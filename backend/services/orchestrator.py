import json
import re
import unicodedata
from collections.abc import AsyncGenerator

from backend.db.queries.channels import get_active_roster, get_channel
from backend.db.queries.messages import (
    get_context_messages,
    get_latest_summary,
    get_total_cost_usd,
    insert_message,
)
from backend.logger import logger
from backend.services.andamio import build_context
from backend.services.compressor import maybe_compress
from backend.services.llm import stream_turn


def _normalize(s: str) -> str:
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()


def parse_mention(text: str, roster: list[dict]) -> dict | None:
    match = re.search(r"@(\S+)", text)
    if not match:
        return None
    mention = _normalize(match.group(1).rstrip(",.!?;:"))
    return next(
        (p for p in roster if _normalize(p["name"]) == mention),
        None,
    )


async def run_turn(
    channel_id: int,
    human_content: str,
    save_human: bool = True,
) -> AsyncGenerator[str, None]:
    await maybe_compress(channel_id)

    if save_human:
        await insert_message(channel_id=channel_id, role="human", content=human_content)

    channel = await get_channel(channel_id)
    roster = await get_active_roster(channel_id)
    profile_names: dict[int, str] = {p["id"]: p["name"] for p in roster}

    if not roster:
        total_cost = await get_total_cost_usd(channel_id)
        yield f"data: {json.dumps({'type': 'TURN_COMPLETE', 'total_cost_usd': str(total_cost)}, ensure_ascii=False)}\n\n"
        return

    logger.info(
        "turn started channel_id={} profiles={}",
        channel_id,
        [p["name"] for p in roster],
    )

    mention = parse_mention(human_content, roster)
    speakers = [mention] if mention else roster

    for profile in speakers:
        summary = await get_latest_summary(channel_id)
        after_id = summary["covers_up_to_msg_id"] if summary else None
        messages = await get_context_messages(channel_id, after_msg_id=after_id)

        system, api_messages = build_context(
            profile=profile,
            channel=channel,
            messages=messages,
            profile_names=profile_names,
            summary=summary,
        )

        yield f"data: {json.dumps({'type': 'start', 'profile_id': profile['id'], 'profile_name': profile['name']}, ensure_ascii=False)}\n\n"

        full_text: list[str] = []
        usage: dict | None = None

        try:
            async for chunk in stream_turn(
                system, api_messages, profile["model"], profile["temperature"]
            ):
                if isinstance(chunk, str):
                    full_text.append(chunk)
                    yield f"data: {json.dumps({'type': 'token', 'profile_id': profile['id'], 'token': chunk}, ensure_ascii=False)}\n\n"
                else:
                    usage = chunk
        except Exception as exc:
            logger.error(
                "stream error channel_id={} profile={}: {}",
                channel_id,
                profile["name"],
                exc,
            )
            raise

        await insert_message(
            channel_id=channel_id,
            role="persona",
            content="".join(full_text),
            profile_id=profile["id"],
            tokens_in=usage["tokens_in"] if usage else None,
            tokens_out=usage["tokens_out"] if usage else None,
            cost_usd=usage["cost_usd"] if usage else None,
        )

        logger.info(
            "turn done profile={} tokens_in={} tokens_out={} cost={}",
            profile["name"],
            usage["tokens_in"] if usage else 0,
            usage["tokens_out"] if usage else 0,
            usage["cost_usd"] if usage else 0,
        )

        yield f"data: {json.dumps({'type': 'done', 'profile_id': profile['id'], 'profile_name': profile['name'], 'tokens_in': usage['tokens_in'] if usage else None, 'tokens_out': usage['tokens_out'] if usage else None, 'cost_usd': str(usage['cost_usd']) if usage else None}, ensure_ascii=False)}\n\n"

    total_cost = await get_total_cost_usd(channel_id)
    yield f"data: {json.dumps({'type': 'TURN_COMPLETE', 'total_cost_usd': str(total_cost)}, ensure_ascii=False)}\n\n"
