# Agora Fase 2B — Compresión, @mención y "Otra ronda" — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add context compression (rolling Haiku summary), @mention speaker filtering, and a "repeat last round" endpoint to the Agora turn orchestrator.

**Architecture:** A new `compressor.py` service handles compression in isolation; `parse_mention` + `_normalize` are added as pure functions to `orchestrator.py`; `run_turn` gains a `save_human` flag and wires everything together; a new `POST /channels/{id}/rounds` endpoint reuses `run_turn` with `save_human=False`.

**Tech Stack:** Python 3.11, FastAPI, aiomysql, `anthropic` SDK (Haiku for compression), `unicodedata` stdlib for accent normalization, pytest-asyncio.

---

## File Map

| Action | File | What changes |
|--------|------|-------------|
| Modify | `backend/db/queries/messages.py` | Add 4 new async functions |
| Create | `backend/services/compressor.py` | `maybe_compress`, `_summarize` |
| Create | `backend/tests/test_compressor.py` | 3 tests for compressor |
| Modify | `backend/services/orchestrator.py` | Add `_normalize`, `parse_mention`, wire `maybe_compress`, `save_human` param |
| Modify | `backend/tests/test_orchestrator.py` | Add `maybe_compress` mock to existing tests + 2 new tests |
| Modify | `backend/api/stream.py` | Add `POST /channels/{id}/rounds` endpoint |
| Modify | `backend/tests/test_stream.py` | Update `_mock_run_turn` signature + 3 new tests |

---

## Task 1: DB queries — messages.py

**Files:**
- Modify: `backend/db/queries/messages.py`

No unit tests for these (DB layer mocked at service layer in this codebase). They will be exercised indirectly by Tasks 2 and 4.

- [ ] **Step 1: Add the 4 new functions**

Open `backend/db/queries/messages.py` and append after the existing `get_total_cost_usd` function:

```python
async def count_messages_after(channel_id: int, after_msg_id: int | None) -> int:
    async with get_db() as cur:
        if after_msg_id is not None:
            await cur.execute(
                "SELECT COUNT(*) AS cnt FROM messages WHERE channel_id = %s AND id > %s",
                (channel_id, after_msg_id),
            )
        else:
            await cur.execute(
                "SELECT COUNT(*) AS cnt FROM messages WHERE channel_id = %s",
                (channel_id,),
            )
        row = await cur.fetchone()
        return int(row["cnt"])


async def get_messages_chunk(
    channel_id: int, after_msg_id: int | None, limit: int
) -> list[dict]:
    async with get_db() as cur:
        if after_msg_id is not None:
            await cur.execute(
                """
                SELECT m.id, m.role, m.profile_id, m.content, p.name AS profile_name
                FROM messages m
                LEFT JOIN profiles p ON m.profile_id = p.id
                WHERE m.channel_id = %s AND m.id > %s
                ORDER BY m.id ASC
                LIMIT %s
                """,
                (channel_id, after_msg_id, limit),
            )
        else:
            await cur.execute(
                """
                SELECT m.id, m.role, m.profile_id, m.content, p.name AS profile_name
                FROM messages m
                LEFT JOIN profiles p ON m.profile_id = p.id
                WHERE m.channel_id = %s
                ORDER BY m.id ASC
                LIMIT %s
                """,
                (channel_id, limit),
            )
        return await cur.fetchall()


async def get_last_human_message(channel_id: int) -> dict | None:
    async with get_db() as cur:
        await cur.execute(
            """
            SELECT * FROM messages
            WHERE channel_id = %s AND role = 'human'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (channel_id,),
        )
        return await cur.fetchone()


async def insert_summary(
    channel_id: int, content: str, covers_up_to_msg_id: int
) -> int:
    async with get_db() as cur:
        await cur.execute(
            """
            INSERT INTO summaries (channel_id, content, covers_up_to_msg_id)
            VALUES (%s, %s, %s)
            """,
            (channel_id, content, covers_up_to_msg_id),
        )
        return cur.lastrowid
```

- [ ] **Step 2: Verify syntax**

```bash
cd /data/agora && python -c "from backend.db.queries.messages import count_messages_after, get_messages_chunk, get_last_human_message, insert_summary; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/db/queries/messages.py
git commit -m "feat: add DB queries for compression and otra-ronda"
```

---

## Task 2: Compressor service

**Files:**
- Create: `backend/services/compressor.py`
- Create: `backend/tests/test_compressor.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_compressor.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_maybe_compress_skips_when_below_threshold():
    from backend.services.compressor import maybe_compress

    with (
        patch(
            "backend.services.compressor.get_latest_summary",
            AsyncMock(return_value=None),
        ),
        patch(
            "backend.services.compressor.count_messages_after",
            AsyncMock(return_value=5),
        ),
        patch("backend.services.compressor.get_messages_chunk") as mock_chunk,
        patch("backend.services.compressor.insert_summary") as mock_insert,
    ):
        await maybe_compress(1)
        mock_chunk.assert_not_called()
        mock_insert.assert_not_called()


@pytest.mark.asyncio
async def test_maybe_compress_compresses_when_at_threshold():
    from backend.services.compressor import maybe_compress

    mock_chunk = [
        {"id": 1, "role": "human", "profile_name": None, "content": "Hola"},
        {"id": 2, "role": "persona", "profile_name": "Sócrates", "content": "Buena pregunta."},
    ]

    with (
        patch(
            "backend.services.compressor.get_latest_summary",
            AsyncMock(return_value=None),
        ),
        patch(
            "backend.services.compressor.count_messages_after",
            AsyncMock(return_value=30),
        ),
        patch(
            "backend.services.compressor.get_messages_chunk",
            AsyncMock(return_value=mock_chunk),
        ),
        patch(
            "backend.services.compressor._summarize",
            AsyncMock(return_value="Resumen del debate."),
        ),
        patch(
            "backend.services.compressor.insert_summary",
            AsyncMock(return_value=1),
        ) as mock_insert,
    ):
        await maybe_compress(1)
        mock_insert.assert_called_once_with(
            1, "Resumen del debate.", covers_up_to_msg_id=2
        )


@pytest.mark.asyncio
async def test_maybe_compress_uses_summary_after_id():
    from backend.services.compressor import maybe_compress

    mock_summary = {"id": 1, "covers_up_to_msg_id": 50, "content": "Prev summary"}

    with (
        patch(
            "backend.services.compressor.get_latest_summary",
            AsyncMock(return_value=mock_summary),
        ),
        patch(
            "backend.services.compressor.count_messages_after",
            AsyncMock(return_value=5),
        ) as mock_count,
        patch("backend.services.compressor.insert_summary") as mock_insert,
    ):
        await maybe_compress(1)
        mock_count.assert_called_once_with(1, 50)
        mock_insert.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /data/agora && python -m pytest backend/tests/test_compressor.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.services.compressor'`

- [ ] **Step 3: Create the compressor service**

Create `backend/services/compressor.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /data/agora && python -m pytest backend/tests/test_compressor.py -v
```

Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/compressor.py backend/tests/test_compressor.py
git commit -m "feat: add compressor service with maybe_compress and Haiku _summarize"
```

---

## Task 3: parse_mention — pure functions in orchestrator

**Files:**
- Modify: `backend/services/orchestrator.py` (add imports + 2 functions at the top only)
- Modify: `backend/tests/test_orchestrator.py` (add 5 new tests)

- [ ] **Step 1: Write the failing tests**

Append these 5 tests at the bottom of `backend/tests/test_orchestrator.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /data/agora && python -m pytest backend/tests/test_orchestrator.py::test_parse_mention_exact_match -v
```

Expected: `ImportError: cannot import name 'parse_mention'`

- [ ] **Step 3: Add imports and pure functions to orchestrator**

At the top of `backend/services/orchestrator.py`, add `re` and `unicodedata` to the existing imports, then add the two functions right before `run_turn`:

```python
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
from backend.services.llm import stream_turn


def _normalize(s: str) -> str:
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()


def parse_mention(text: str, roster: list[dict]) -> dict | None:
    match = re.search(r"@(\S+)", text)
    if not match:
        return None
    mention = _normalize(match.group(1))
    return next(
        (p for p in roster if _normalize(p["name"]) == mention),
        None,
    )
```

Do NOT change `run_turn` yet — that is Task 4.

- [ ] **Step 4: Run the 5 new tests**

```bash
cd /data/agora && python -m pytest backend/tests/test_orchestrator.py -k "parse_mention" -v
```

Expected: 5 tests PASS

- [ ] **Step 5: Run the full test suite to confirm no regressions**

```bash
cd /data/agora && python -m pytest backend/tests/ -v
```

Expected: all existing tests still PASS

- [ ] **Step 6: Commit**

```bash
git add backend/services/orchestrator.py backend/tests/test_orchestrator.py
git commit -m "feat: add parse_mention with accent+case-insensitive matching"
```

---

## Task 4: Wire orchestrator — save_human flag, maybe_compress, parse_mention filter

**Files:**
- Modify: `backend/services/orchestrator.py` (full rewrite of `run_turn`)
- Modify: `backend/tests/test_orchestrator.py` (add `maybe_compress` mock to all existing `run_turn` tests + 2 new tests)

- [ ] **Step 1: Write the 2 new failing tests**

Append these 2 tests at the bottom of `backend/tests/test_orchestrator.py` (the `MOCK_ROSTER_TWO` constant is defined inline):

```python
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
```

- [ ] **Step 2: Run new tests to verify they fail**

```bash
cd /data/agora && python -m pytest backend/tests/test_orchestrator.py::test_run_turn_save_human_false_skips_human_insert backend/tests/test_orchestrator.py::test_run_turn_mention_filters_to_one_speaker -v
```

Expected: both FAIL (run_turn doesn't have `save_human` param yet, `maybe_compress` not imported)

- [ ] **Step 3: Rewrite run_turn in orchestrator.py**

Replace the existing `run_turn` function (everything from `async def run_turn` to the end of the file) with:

```python
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
```

Also add the import for `maybe_compress` at the top of the file (after the existing imports):

```python
from backend.services.compressor import maybe_compress
```

- [ ] **Step 4: Add `maybe_compress` mock to the 3 existing run_turn tests**

The 3 existing tests — `test_run_turn_yields_sse_start_tokens_done`, `test_run_turn_saves_human_message_first`, `test_run_turn_empty_roster_yields_only_turn_complete` — each need this mock added inside their `with (...)` block:

```python
patch("backend.services.orchestrator.maybe_compress", AsyncMock()),
```

Add it as the first `patch` in each `with` block. The function signature stays the same — just a new mock for the new dependency.

- [ ] **Step 5: Run all orchestrator tests**

```bash
cd /data/agora && python -m pytest backend/tests/test_orchestrator.py -v
```

Expected: all 10 tests PASS (5 parse_mention + 3 existing run_turn + 2 new run_turn)

- [ ] **Step 6: Run full test suite**

```bash
cd /data/agora && python -m pytest backend/tests/ -v
```

Expected: all tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/services/orchestrator.py backend/tests/test_orchestrator.py
git commit -m "feat: wire maybe_compress, parse_mention, and save_human into run_turn"
```

---

## Task 5: "Otra ronda" endpoint

**Files:**
- Modify: `backend/api/stream.py`
- Modify: `backend/tests/test_stream.py`

- [ ] **Step 1: Write the failing tests**

First update `_mock_run_turn` in `backend/tests/test_stream.py` — add the `save_human` parameter so it accepts the kwarg without error:

```python
async def _mock_run_turn(channel_id: int, human_content: str, save_human: bool = True):
    yield f"data: {json.dumps({'type': 'start', 'profile_id': 1, 'profile_name': 'Sócrates'}, ensure_ascii=False)}\n\n"
    yield f"data: {json.dumps({'type': 'token', 'profile_id': 1, 'token': 'Hola'}, ensure_ascii=False)}\n\n"
    yield f"data: {json.dumps({'type': 'done', 'profile_id': 1, 'profile_name': 'Sócrates', 'tokens_in': 5, 'tokens_out': 3, 'cost_usd': '0.000009'}, ensure_ascii=False)}\n\n"
    yield f"data: {json.dumps({'type': 'TURN_COMPLETE', 'total_cost_usd': '0.000009'}, ensure_ascii=False)}\n\n"
```

Then add the constant and 3 new tests at the bottom of `backend/tests/test_stream.py`:

```python
MOCK_HUMAN_MSG = {"id": 5, "role": "human", "content": "¿SaaS?", "channel_id": 1}


@pytest.mark.asyncio
async def test_post_round_streams_sse():
    from backend.main import app

    with (
        patch("backend.api.stream.get_channel", AsyncMock(return_value=MOCK_CHANNEL)),
        patch(
            "backend.api.stream.get_last_human_message",
            AsyncMock(return_value=MOCK_HUMAN_MSG),
        ),
        patch("backend.api.stream.run_turn", _mock_run_turn),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            async with ac.stream("POST", "/channels/1/rounds") as resp:
                assert resp.status_code == 200
                assert "text/event-stream" in resp.headers["content-type"]
                body = ""
                async for chunk in resp.aiter_text():
                    body += chunk

    assert "TURN_COMPLETE" in body


@pytest.mark.asyncio
async def test_post_round_404_unknown_channel():
    from backend.main import app

    with patch("backend.api.stream.get_channel", AsyncMock(return_value=None)):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.post("/channels/999/rounds")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_post_round_400_no_human_messages():
    from backend.main import app

    with (
        patch("backend.api.stream.get_channel", AsyncMock(return_value=MOCK_CHANNEL)),
        patch(
            "backend.api.stream.get_last_human_message",
            AsyncMock(return_value=None),
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.post("/channels/1/rounds")
    assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /data/agora && python -m pytest backend/tests/test_stream.py::test_post_round_streams_sse backend/tests/test_stream.py::test_post_round_404_unknown_channel backend/tests/test_stream.py::test_post_round_400_no_human_messages -v
```

Expected: all 3 FAIL (endpoint does not exist yet)

- [ ] **Step 3: Add the endpoint to stream.py**

Replace the full content of `backend/api/stream.py` with:

```python
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.db.queries.channels import get_channel
from backend.db.queries.messages import get_last_human_message
from backend.schemas.models import TurnRequest
from backend.services.orchestrator import run_turn

router = APIRouter()


@router.post("/channels/{channel_id}/messages")
async def post_message(channel_id: int, request: TurnRequest) -> StreamingResponse:
    channel = await get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")

    return StreamingResponse(
        run_turn(channel_id, request.content),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/channels/{channel_id}/rounds")
async def post_round(channel_id: int) -> StreamingResponse:
    channel = await get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")

    last_msg = await get_last_human_message(channel_id)
    if not last_msg:
        raise HTTPException(status_code=400, detail="No hay mensajes en este canal")

    return StreamingResponse(
        run_turn(channel_id, last_msg["content"], save_human=False),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
```

- [ ] **Step 4: Run the 3 new stream tests**

```bash
cd /data/agora && python -m pytest backend/tests/test_stream.py -v
```

Expected: all 5 stream tests PASS (2 existing + 3 new)

- [ ] **Step 5: Run the full test suite**

```bash
cd /data/agora && python -m pytest backend/tests/ -v
```

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/api/stream.py backend/tests/test_stream.py
git commit -m "feat: add POST /channels/{id}/rounds endpoint for otra-ronda"
```

---

## Done

All 5 tasks complete. The full test suite should pass. Proceed to superpowers:finishing-a-development-branch.
