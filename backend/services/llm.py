from collections.abc import AsyncGenerator
from decimal import Decimal

import anthropic

from backend.config import settings

client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

# Prices per token (input/output) in USD. Verify when updating models.
_COST_PER_TOKEN: dict[str, dict[str, float]] = {
    "claude-haiku-4-5-20251001": {"in": 0.8e-6, "out": 4e-6},
    "claude-sonnet-4-6": {"in": 3e-6, "out": 15e-6},
    "claude-opus-4-8": {"in": 15e-6, "out": 75e-6},
}


async def stream_turn(
    system: str,
    messages: list[dict],
    model: str,
    temperature: float,
) -> AsyncGenerator:
    """
    Yields str tokens until exhausted, then yields a dict with usage stats.

    Final dict shape: {tokens_in: int, tokens_out: int, cost_usd: Decimal}
    """
    async with client.messages.stream(
        model=model,
        max_tokens=1024,
        system=system,
        messages=messages,
        temperature=float(temperature),
    ) as stream:
        async for text in stream.text_stream:
            yield text

        final = await stream.get_final_message()
        tokens_in = final.usage.input_tokens
        tokens_out = final.usage.output_tokens
        prices = _COST_PER_TOKEN.get(model, {"in": 0.0, "out": 0.0})
        cost = Decimal(
            str(round(tokens_in * prices["in"] + tokens_out * prices["out"], 8))
        )
        yield {"tokens_in": tokens_in, "tokens_out": tokens_out, "cost_usd": cost}
