import json
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest


async def _mock_stream_turn(system, messages, model, temperature):
    yield "Buena"
    yield " pregunta."
    yield {"tokens_in": 10, "tokens_out": 5, "cost_usd": Decimal("0.000010")}


MOCK_CHANNEL = {"id": 1, "mode": "debate", "title": "Test", "incognito": False}
MOCK_ROSTER = [
    {
        "id": 1,
        "name": "Sócrates",
        "tipo": "tertuliano",
        "model": "claude-sonnet-4-6",
        "temperature": 0.7,
        "system_prompt": "Eres Sócrates.",
        "speaking_order": 0,
        "archived": False,
        "color": "gris",
    }
]


@pytest.mark.asyncio
async def test_run_turn_yields_sse_start_tokens_done():
    from backend.services.orchestrator import run_turn

    with (
        patch(
            "backend.services.orchestrator.insert_message", AsyncMock(return_value=42)
        ),
        patch(
            "backend.services.orchestrator.get_channel",
            AsyncMock(return_value=MOCK_CHANNEL),
        ),
        patch(
            "backend.services.orchestrator.get_active_roster",
            AsyncMock(return_value=MOCK_ROSTER),
        ),
        patch(
            "backend.services.orchestrator.get_latest_summary",
            AsyncMock(return_value=None),
        ),
        patch(
            "backend.services.orchestrator.get_context_messages",
            AsyncMock(return_value=[]),
        ),
        patch("backend.services.orchestrator.stream_turn", _mock_stream_turn),
    ):
        chunks = []
        async for chunk in run_turn(1, "¿SaaS?"):
            chunks.append(chunk)

    # Parse SSE events (skip TURN_COMPLETE sentinel)
    events = [
        json.loads(c.removeprefix("data: ").strip())
        for c in chunks
        if c.startswith("data:") and "[TURN_COMPLETE]" not in c
    ]
    turn_complete = any("[TURN_COMPLETE]" in c for c in chunks)

    types = [e["type"] for e in events]
    assert "start" in types
    assert "token" in types
    assert "done" in types
    assert turn_complete

    token_events = [e for e in events if e["type"] == "token"]
    combined = "".join(e["token"] for e in token_events)
    assert combined == "Buena pregunta."

    done_event = next(e for e in events if e["type"] == "done")
    assert done_event["profile_id"] == 1
    assert done_event["tokens_in"] == 10


@pytest.mark.asyncio
async def test_run_turn_saves_human_message_first():
    from backend.services.orchestrator import run_turn

    insert_mock = AsyncMock(return_value=99)
    with (
        patch("backend.services.orchestrator.insert_message", insert_mock),
        patch(
            "backend.services.orchestrator.get_channel",
            AsyncMock(return_value=MOCK_CHANNEL),
        ),
        patch(
            "backend.services.orchestrator.get_active_roster",
            AsyncMock(return_value=MOCK_ROSTER),
        ),
        patch(
            "backend.services.orchestrator.get_latest_summary",
            AsyncMock(return_value=None),
        ),
        patch(
            "backend.services.orchestrator.get_context_messages",
            AsyncMock(return_value=[]),
        ),
        patch("backend.services.orchestrator.stream_turn", _mock_stream_turn),
    ):
        async for _ in run_turn(1, "Hola"):
            pass

    first_call = insert_mock.call_args_list[0]
    assert first_call.kwargs["role"] == "human"
    assert first_call.kwargs["content"] == "Hola"
