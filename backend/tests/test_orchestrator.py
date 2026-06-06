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
        patch("backend.services.orchestrator.maybe_compress", AsyncMock()),
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
        patch(
            "backend.services.orchestrator.get_total_cost_usd",
            AsyncMock(return_value=Decimal("0.000010")),
        ),
    ):
        chunks = []
        async for chunk in run_turn(1, "¿SaaS?"):
            chunks.append(chunk)

    # Parse all SSE events
    events = [
        json.loads(c.removeprefix("data: ").strip())
        for c in chunks
        if c.startswith("data:")
    ]
    types = [e["type"] for e in events]

    assert "start" in types
    assert "token" in types
    assert "done" in types
    assert "TURN_COMPLETE" in types

    token_events = [e for e in events if e["type"] == "token"]
    assert "".join(e["token"] for e in token_events) == "Buena pregunta."

    done_event = next(e for e in events if e["type"] == "done")
    assert done_event["profile_id"] == 1
    assert done_event["tokens_in"] == 10
    assert done_event["cost_usd"] == "0.000010"

    tc_event = next(e for e in events if e["type"] == "TURN_COMPLETE")
    assert "total_cost_usd" in tc_event


@pytest.mark.asyncio
async def test_run_turn_saves_human_message_first():
    from backend.services.orchestrator import run_turn

    insert_mock = AsyncMock(return_value=99)
    with (
        patch("backend.services.orchestrator.maybe_compress", AsyncMock()),
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
        patch(
            "backend.services.orchestrator.get_total_cost_usd",
            AsyncMock(return_value=Decimal("0")),
        ),
    ):
        async for _ in run_turn(1, "Hola"):
            pass

    first_call = insert_mock.call_args_list[0]
    assert first_call.kwargs["role"] == "human"
    assert first_call.kwargs["content"] == "Hola"


@pytest.mark.asyncio
async def test_run_turn_empty_roster_yields_only_turn_complete():
    from backend.services.orchestrator import run_turn

    with (
        patch("backend.services.orchestrator.maybe_compress", AsyncMock()),
        patch(
            "backend.services.orchestrator.insert_message", AsyncMock(return_value=1)
        ),
        patch(
            "backend.services.orchestrator.get_channel",
            AsyncMock(return_value=MOCK_CHANNEL),
        ),
        patch(
            "backend.services.orchestrator.get_active_roster",
            AsyncMock(return_value=[]),
        ),
        patch(
            "backend.services.orchestrator.get_total_cost_usd",
            AsyncMock(return_value=Decimal("0")),
        ),
    ):
        chunks = []
        async for chunk in run_turn(1, "Hola"):
            chunks.append(chunk)

    assert len(chunks) == 1
    event = json.loads(chunks[0].removeprefix("data: ").strip())
    assert event["type"] == "TURN_COMPLETE"
    assert event["total_cost_usd"] == "0"


def test_parse_mention_exact_match():
    from backend.services.orchestrator import parse_mention

    roster = [{"id": 1, "name": "Sócrates"}, {"id": 2, "name": "Platón"}]
    result = parse_mention("Hola @Sócrates, ¿qué piensas?", roster)
    assert result is not None
    assert result["id"] == 1


def test_parse_mention_accent_insensitive():
    from backend.services.orchestrator import parse_mention

    roster = [{"id": 1, "name": "Sócrates"}]
    result = parse_mention("@Socrates qué piensas?", roster)
    assert result is not None
    assert result["id"] == 1


def test_parse_mention_case_insensitive():
    from backend.services.orchestrator import parse_mention

    roster = [{"id": 1, "name": "Sócrates"}]
    result = parse_mention("@SOCRATES", roster)
    assert result is not None
    assert result["id"] == 1


def test_parse_mention_no_match_returns_none():
    from backend.services.orchestrator import parse_mention

    roster = [{"id": 1, "name": "Sócrates"}]
    result = parse_mention("@Aristoteles qué piensas?", roster)
    assert result is None


def test_parse_mention_no_at_symbol():
    from backend.services.orchestrator import parse_mention

    roster = [{"id": 1, "name": "Sócrates"}]
    result = parse_mention("Hola Sócrates", roster)
    assert result is None


@pytest.mark.asyncio
async def test_run_turn_save_human_false_skips_human_insert():
    from backend.services.orchestrator import run_turn

    insert_mock = AsyncMock(return_value=99)
    with (
        patch("backend.services.orchestrator.maybe_compress", AsyncMock()),
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
        patch(
            "backend.services.orchestrator.get_total_cost_usd",
            AsyncMock(return_value=Decimal("0")),
        ),
    ):
        async for _ in run_turn(1, "Hola", save_human=False):
            pass

    roles = [call.kwargs["role"] for call in insert_mock.call_args_list]
    assert "human" not in roles
    assert "persona" in roles


@pytest.mark.asyncio
async def test_run_turn_mention_filters_to_one_speaker():
    from backend.services.orchestrator import run_turn

    roster_two = [
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
        },
        {
            "id": 2,
            "name": "Platón",
            "tipo": "tertuliano",
            "model": "claude-sonnet-4-6",
            "temperature": 0.7,
            "system_prompt": "Eres Platón.",
            "speaking_order": 1,
            "archived": False,
            "color": "azul",
        },
    ]

    with (
        patch("backend.services.orchestrator.maybe_compress", AsyncMock()),
        patch(
            "backend.services.orchestrator.insert_message", AsyncMock(return_value=1)
        ),
        patch(
            "backend.services.orchestrator.get_channel",
            AsyncMock(return_value=MOCK_CHANNEL),
        ),
        patch(
            "backend.services.orchestrator.get_active_roster",
            AsyncMock(return_value=roster_two),
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
        patch(
            "backend.services.orchestrator.get_total_cost_usd",
            AsyncMock(return_value=Decimal("0")),
        ),
    ):
        chunks = []
        async for chunk in run_turn(1, "@Socrates qué piensas?"):
            chunks.append(chunk)

    events = [
        json.loads(c.removeprefix("data: ").strip())
        for c in chunks
        if c.startswith("data:")
    ]
    start_events = [e for e in events if e["type"] == "start"]
    assert len(start_events) == 1
    assert start_events[0]["profile_name"] == "Sócrates"
