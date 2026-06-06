from anthropic import AsyncAnthropic

from backend.config import settings
from backend.db.queries.messages import (
    count_messages_after,
    get_latest_summary,
    get_messages_chunk,
    insert_summary,
)

COMPRESSION_THRESHOLD = 30
COMPRESSION_CHUNK = 20
_HAIKU = "claude-haiku-4-5-20251001"

_client = AsyncAnthropic(api_key=settings.anthropic_api_key)


async def maybe_compress(channel_id: int) -> None:
    summary = await get_latest_summary(channel_id)
    after_id = summary["covers_up_to_msg_id"] if summary else None
    count = await count_messages_after(channel_id, after_id)
    if count < COMPRESSION_THRESHOLD:
        return
    chunk = await get_messages_chunk(channel_id, after_id, limit=COMPRESSION_CHUNK)
    if not chunk:
        return  # nothing to compress
    text = await _summarize(chunk)
    last_id = chunk[-1]["id"]
    await insert_summary(channel_id, text, covers_up_to_msg_id=last_id)


async def _summarize(messages: list[dict]) -> str:
    lines = [f"{m['profile_name'] or m['role']}: {m['content']}" for m in messages]
    transcript = "\n".join(lines)
    response = await _client.messages.create(
        model=_HAIKU,
        max_tokens=512,
        system=(
            "Eres un compresor de transcripciones. Resume el siguiente fragmento de "
            "conversación de forma neutral, compacta y en tercera persona. "
            "Preserva los argumentos clave y las posiciones de cada hablante."
        ),
        messages=[{"role": "user", "content": transcript}],
    )
    return response.content[0].text
