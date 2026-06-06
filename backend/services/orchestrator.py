import json
from collections.abc import AsyncGenerator
from decimal import Decimal

from backend.db.queries.channels import get_active_roster, get_channel
from backend.db.queries.messages import (
    get_context_messages,
    get_latest_summary,
    insert_message,
)
from backend.services.andamio import build_context
from backend.services.llm import stream_turn


async def run_turn(channel_id: int, human_content: str) -> AsyncGenerator[str, None]:
    """
    Full turn lifecycle (D1 from design doc):
    1. Save human message.
    2. For each active tertuliano in speaking_order:
       a. Build context (andamio matrix + history).
       b. Stream Anthropic response — yield SSE tokens.
       c. Save persona message with cost.
    3. Yield TURN_COMPLETE sentinel.
    """
    await insert_message(channel_id=channel_id, role="human", content=human_content)

    channel = await get_channel(channel_id)
    roster = await get_active_roster(channel_id)
    profile_names: dict[int, str] = {p["id"]: p["name"] for p in roster}

    for profile in roster:
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

        async for chunk in stream_turn(
            system, api_messages, profile["model"], profile["temperature"]
        ):
            if isinstance(chunk, str):
                full_text.append(chunk)
                yield f"data: {json.dumps({'type': 'token', 'profile_id': profile['id'], 'token': chunk}, ensure_ascii=False)}\n\n"
            else:
                usage = chunk

        await insert_message(
            channel_id=channel_id,
            role="persona",
            content="".join(full_text),
            profile_id=profile["id"],
            tokens_in=usage["tokens_in"] if usage else None,
            tokens_out=usage["tokens_out"] if usage else None,
            cost_usd=usage["cost_usd"] if usage else None,
        )

        yield f"data: {json.dumps({'type': 'done', 'profile_id': profile['id'], 'profile_name': profile['name'], 'tokens_in': usage['tokens_in'] if usage else None, 'tokens_out': usage['tokens_out'] if usage else None, 'cost_usd': str(usage['cost_usd']) if usage else None}, ensure_ascii=False)}\n\n"

    yield "data: [TURN_COMPLETE]\n\n"
