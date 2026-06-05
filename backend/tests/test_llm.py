from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


async def _aiter(*items):
    for item in items:
        yield item


@pytest.mark.asyncio
async def test_stream_turn_yields_tokens_then_usage():
    from backend.services.llm import stream_turn

    mock_final = MagicMock()
    mock_final.usage.input_tokens = 10
    mock_final.usage.output_tokens = 5

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_ctx.text_stream = _aiter("Buena", " pregunta.")
    mock_ctx.get_final_message = AsyncMock(return_value=mock_final)

    with patch("backend.services.llm.client.messages.stream", return_value=mock_ctx):
        chunks = []
        async for chunk in stream_turn(
            system="Test",
            messages=[{"role": "user", "content": "hola"}],
            model="claude-haiku-4-5-20251001",
            temperature=0.7,
        ):
            chunks.append(chunk)

    assert chunks[0] == "Buena"
    assert chunks[1] == " pregunta."
    usage = chunks[2]
    assert isinstance(usage, dict)
    assert usage["tokens_in"] == 10
    assert usage["tokens_out"] == 5
    assert isinstance(usage["cost_usd"], Decimal)
    assert usage["cost_usd"] > 0


@pytest.mark.asyncio
async def test_stream_turn_cost_zero_for_unknown_model():
    from backend.services.llm import stream_turn

    mock_final = MagicMock()
    mock_final.usage.input_tokens = 5
    mock_final.usage.output_tokens = 3

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_ctx.text_stream = _aiter("ok")
    mock_ctx.get_final_message = AsyncMock(return_value=mock_final)

    with patch("backend.services.llm.client.messages.stream", return_value=mock_ctx):
        chunks = []
        async for chunk in stream_turn(
            "s", [{"role": "user", "content": "x"}], "unknown-model", 0.5
        ):
            chunks.append(chunk)

    usage = chunks[-1]
    assert usage["cost_usd"] == Decimal("0")
