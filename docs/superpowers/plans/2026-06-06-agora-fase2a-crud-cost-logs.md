# Agora Fase 2A — CRUD + Coste en Vivo + LogCentral

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir la API REST de perfiles, canales y roster; exponer el coste acumulado en el evento TURN_COMPLETE del SSE; e integrar LogCentral (loguru → JSON sink → Vector).

**Architecture:** Routers separados por recurso (`api/profiles.py`, `api/channels.py`) sobre la capa de queries ya existente. El orchestrator sigue siendo el único productor de SSE — solo cambia el evento TURN_COMPLETE a JSON con `total_cost_usd`. LogCentral es un JSON sink de loguru que escribe a `logs/tertulia.log` sin dependencias de paquete adicionales.

**Tech Stack:** FastAPI 0.115+, Pydantic v2, aiomysql, loguru, pytest + pytest-asyncio (auto mode), httpx para tests de endpoint.

---

## Mapa de ficheros

```
backend/
├── logger.py                         NUEVO — JSON sink loguru → logs/tertulia.log
├── main.py                           MODIFY — importar routers nuevos + logger en lifespan
├── requirements.txt                  MODIFY — añadir loguru>=0.7.0
├── schemas/
│   └── models.py                     MODIFY — ProfileIn/Out/Patch, ChannelIn/Out/Patch, RosterAddIn/Patch/Entry
├── db/
│   └── queries/
│       ├── profiles.py               NUEVO — get_profile, list_profiles, insert_profile, update_profile, archive_profile
│       ├── channels.py               MODIFY — list_channels, insert_channel, update_channel, get_full_roster, add_to_roster, remove_from_roster, update_roster_entry, get_roster_entry, count_active_roster
│       └── messages.py               MODIFY — get_total_cost_usd
├── api/
│   ├── profiles.py                   NUEVO — router /profiles
│   └── channels.py                   NUEVO — router /channels (CRUD + roster)
├── services/
│   └── orchestrator.py              MODIFY — TURN_COMPLETE → JSON con total_cost_usd, logs
└── tests/
    ├── test_profiles_api.py          NUEVO — 7 tests
    ├── test_channels_api.py          NUEVO — 10 tests
    ├── test_orchestrator.py          MODIFY — TURN_COMPLETE assertions, mock get_total_cost_usd
    └── test_stream.py               MODIFY — actualizar mock TURN_COMPLETE
```

**Contratos nuevos:**
- `db/queries/profiles.py`: todas las funciones reciben tipos primitivos (str, float, etc.), no dicts Pydantic
- `db/queries/channels.py`: `update_profile`/`update_channel`/`update_roster_entry` reciben `fields: dict` con claves ya validadas por Pydantic (safe, no SQL injection)
- `orchestrator.run_turn` sigue siendo `AsyncGenerator[str, None]`; el último yield cambia de `"data: [TURN_COMPLETE]\n\n"` a `"data: {"type":"TURN_COMPLETE","total_cost_usd":"..."}\n\n"`

---

## Task 1: LogCentral — `backend/logger.py`

**Files:**
- Create: `backend/logger.py`
- Modify: `backend/requirements.txt`

*(Sin TDD — es infraestructura pura. Verificación por importación.)*

- [ ] **Step 1: Añadir loguru a `backend/requirements.txt`**

```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
anthropic>=0.40.0
aiomysql>=0.2.0
pydantic-settings>=2.0.0
loguru>=0.7.0
pytest>=8.0.0
pytest-asyncio>=0.24.0
httpx>=0.27.0
```

- [ ] **Step 2: Instalar**

```bash
cd /data/agora && .venv/bin/pip install loguru>=0.7.0 -q
```

- [ ] **Step 3: Crear `backend/logger.py`**

```python
import json
from datetime import timezone
from pathlib import Path

from loguru import logger

_log_path = Path("logs/tertulia.log")
_log_path.parent.mkdir(parents=True, exist_ok=True)


def _json_sink(message):
    record = message.record
    entry = {
        "timestamp": record["time"].astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "level": record["level"].name,
        "source": "tertulia",
        "message": record["message"],
    }
    with open(_log_path, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


logger.add(_json_sink, level="INFO")
```

- [ ] **Step 4: Verificar que el import funciona**

```bash
cd /data/agora && PYTHONPATH=/data/agora .venv/bin/python -c "from backend.logger import logger; logger.info('test ok'); print('logger OK')"
```

Esperado: `logger OK` (sin excepciones). Verifica también que se creó `logs/tertulia.log`:

```bash
cat /data/agora/logs/tertulia.log
```

Esperado: una línea JSON con `"source": "tertulia"` y `"message": "test ok"`.

- [ ] **Step 5: Commit**

```bash
git add backend/logger.py backend/requirements.txt logs/
git commit -m "feat: LogCentral JSON sink (loguru → logs/tertulia.log)"
```

---

## Task 2: DB queries — `backend/db/queries/profiles.py`

**Files:**
- Create: `backend/db/queries/profiles.py`

*(Sin unit tests — la capa de queries se verifica a través de los tests de API en Task 5 que mockean estas funciones. La integración real se verifica en Task 8.)*

- [ ] **Step 1: Crear `backend/db/queries/profiles.py`**

```python
from backend.db.connection import get_db

_UPDATABLE_FIELDS = frozenset({"name", "model", "temperature", "color", "funcion", "system_prompt"})


async def get_profile(profile_id: int) -> dict | None:
    async with get_db() as cur:
        await cur.execute("SELECT * FROM profiles WHERE id = %s", (profile_id,))
        return await cur.fetchone()


async def list_profiles() -> list[dict]:
    async with get_db() as cur:
        await cur.execute(
            "SELECT * FROM profiles WHERE archived = FALSE ORDER BY id"
        )
        return await cur.fetchall()


async def insert_profile(
    name: str,
    tipo: str,
    model: str,
    temperature: float,
    color: str | None,
    funcion: str,
    system_prompt: str,
) -> int:
    async with get_db() as cur:
        await cur.execute(
            """
            INSERT INTO profiles (name, tipo, model, temperature, color, funcion, system_prompt)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (name, tipo, model, temperature, color, funcion, system_prompt),
        )
        return cur.lastrowid


async def update_profile(profile_id: int, fields: dict) -> None:
    if not fields:
        return
    set_clause = ", ".join(f"{k} = %s" for k in fields)
    values = list(fields.values()) + [profile_id]
    async with get_db() as cur:
        await cur.execute(
            f"UPDATE profiles SET {set_clause} WHERE id = %s", values
        )


async def archive_profile(profile_id: int) -> None:
    async with get_db() as cur:
        await cur.execute(
            "UPDATE profiles SET archived = TRUE WHERE id = %s", (profile_id,)
        )
```

- [ ] **Step 2: Verificar que el módulo importa sin errores**

```bash
cd /data/agora && PYTHONPATH=/data/agora .venv/bin/python -c "from backend.db.queries.profiles import get_profile, list_profiles, insert_profile, update_profile, archive_profile; print('OK')"
```

Esperado: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/db/queries/profiles.py
git commit -m "feat: profiles DB queries (get, list, insert, update, archive)"
```

---

## Task 3: DB queries — ampliación de `channels.py` y `messages.py`

**Files:**
- Modify: `backend/db/queries/channels.py`
- Modify: `backend/db/queries/messages.py`

- [ ] **Step 1: Reemplazar `backend/db/queries/channels.py` con la versión completa**

```python
from backend.db.connection import get_db


async def get_channel(channel_id: int) -> dict | None:
    async with get_db() as cur:
        await cur.execute("SELECT * FROM channels WHERE id = %s", (channel_id,))
        return await cur.fetchone()


async def list_channels() -> list[dict]:
    async with get_db() as cur:
        await cur.execute("SELECT * FROM channels ORDER BY id")
        return await cur.fetchall()


async def insert_channel(title: str, mode: str, incognito: bool) -> int:
    async with get_db() as cur:
        await cur.execute(
            "INSERT INTO channels (title, mode, incognito) VALUES (%s, %s, %s)",
            (title, mode, incognito),
        )
        return cur.lastrowid


async def update_channel(channel_id: int, fields: dict) -> None:
    if not fields:
        return
    set_clause = ", ".join(f"{k} = %s" for k in fields)
    values = list(fields.values()) + [channel_id]
    async with get_db() as cur:
        await cur.execute(
            f"UPDATE channels SET {set_clause} WHERE id = %s", values
        )


async def get_active_roster(channel_id: int) -> list[dict]:
    async with get_db() as cur:
        await cur.execute(
            """
            SELECT p.*, cp.speaking_order
            FROM channel_profiles cp
            JOIN profiles p ON p.id = cp.profile_id
            WHERE cp.channel_id = %s
              AND cp.active = TRUE
              AND p.archived = FALSE
            ORDER BY cp.speaking_order
            """,
            (channel_id,),
        )
        return await cur.fetchall()


async def get_full_roster(channel_id: int) -> list[dict]:
    async with get_db() as cur:
        await cur.execute(
            """
            SELECT p.id AS profile_id, p.name, p.tipo, cp.speaking_order, cp.active
            FROM channel_profiles cp
            JOIN profiles p ON p.id = cp.profile_id
            WHERE cp.channel_id = %s AND cp.active = TRUE
            ORDER BY cp.speaking_order
            """,
            (channel_id,),
        )
        return await cur.fetchall()


async def get_roster_entry(channel_id: int, profile_id: int) -> dict | None:
    async with get_db() as cur:
        await cur.execute(
            """
            SELECT p.id AS profile_id, p.name, p.tipo, cp.speaking_order, cp.active
            FROM channel_profiles cp
            JOIN profiles p ON p.id = cp.profile_id
            WHERE cp.channel_id = %s AND cp.profile_id = %s
            """,
            (channel_id, profile_id),
        )
        return await cur.fetchone()


async def count_active_roster(channel_id: int) -> int:
    async with get_db() as cur:
        await cur.execute(
            "SELECT COUNT(*) AS cnt FROM channel_profiles WHERE channel_id = %s AND active = TRUE",
            (channel_id,),
        )
        row = await cur.fetchone()
        return row["cnt"]


async def add_to_roster(channel_id: int, profile_id: int, speaking_order: int) -> None:
    async with get_db() as cur:
        await cur.execute(
            """
            INSERT INTO channel_profiles (channel_id, profile_id, speaking_order)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE active = TRUE, speaking_order = %s
            """,
            (channel_id, profile_id, speaking_order, speaking_order),
        )


async def remove_from_roster(channel_id: int, profile_id: int) -> None:
    async with get_db() as cur:
        await cur.execute(
            "UPDATE channel_profiles SET active = FALSE WHERE channel_id = %s AND profile_id = %s",
            (channel_id, profile_id),
        )


async def update_roster_entry(channel_id: int, profile_id: int, fields: dict) -> None:
    if not fields:
        return
    set_clause = ", ".join(f"{k} = %s" for k in fields)
    values = list(fields.values()) + [channel_id, profile_id]
    async with get_db() as cur:
        await cur.execute(
            f"UPDATE channel_profiles SET {set_clause} WHERE channel_id = %s AND profile_id = %s",
            values,
        )
```

- [ ] **Step 2: Añadir `get_total_cost_usd` al final de `backend/db/queries/messages.py`**

Añadir después de `get_latest_summary`:

```python
async def get_total_cost_usd(channel_id: int) -> Decimal:
    async with get_db() as cur:
        await cur.execute(
            "SELECT COALESCE(SUM(cost_usd), 0) AS total FROM messages WHERE channel_id = %s",
            (channel_id,),
        )
        row = await cur.fetchone()
        return Decimal(str(row["total"]))
```

- [ ] **Step 3: Verificar imports**

```bash
cd /data/agora && PYTHONPATH=/data/agora .venv/bin/python -c "
from backend.db.queries.channels import (list_channels, insert_channel, update_channel, get_full_roster, get_roster_entry, count_active_roster, add_to_roster, remove_from_roster, update_roster_entry)
from backend.db.queries.messages import get_total_cost_usd
print('OK')
"
```

Esperado: `OK`

- [ ] **Step 4: Tests existentes siguen pasando**

```bash
cd /data/agora && .venv/bin/python -m pytest -v --tb=short -q
```

Esperado: `15 passed` (los cambios a channels.py son aditivos; get_active_roster no cambia).

- [ ] **Step 5: Commit**

```bash
git add backend/db/queries/channels.py backend/db/queries/messages.py
git commit -m "feat: channels/roster/messages DB queries for Fase 2A"
```

---

## Task 4: Schemas — ampliar `backend/schemas/models.py`

**Files:**
- Modify: `backend/schemas/models.py`

- [ ] **Step 1: Reemplazar `backend/schemas/models.py` con la versión completa**

```python
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class TurnRequest(BaseModel):
    content: str


# --- Profiles ---


class ProfileIn(BaseModel):
    name: str
    tipo: Literal["tertuliano", "facilitador"] = "tertuliano"
    model: str = "claude-sonnet-4-6"
    temperature: float = 0.7
    color: str | None = None
    funcion: str
    system_prompt: str


class ProfileOut(BaseModel):
    id: int
    name: str
    tipo: str
    model: str
    temperature: float
    color: str | None
    funcion: str
    system_prompt: str
    archived: bool
    created_at: datetime
    updated_at: datetime


class ProfilePatch(BaseModel):
    name: str | None = None
    model: str | None = None
    temperature: float | None = None
    color: str | None = None
    funcion: str | None = None
    system_prompt: str | None = None


# --- Channels ---


class ChannelIn(BaseModel):
    title: str
    mode: Literal["debate", "critica"] = "debate"
    incognito: bool = False


class ChannelOut(BaseModel):
    id: int
    title: str
    mode: str
    incognito: bool
    created_at: datetime


class ChannelPatch(BaseModel):
    title: str | None = None
    mode: Literal["debate", "critica"] | None = None
    incognito: bool | None = None


# --- Roster ---


class RosterAddIn(BaseModel):
    profile_id: int
    speaking_order: int = 0


class RosterPatch(BaseModel):
    speaking_order: int | None = None
    active: bool | None = None


class RosterEntry(BaseModel):
    profile_id: int
    name: str
    tipo: str
    speaking_order: int
    active: bool
```

- [ ] **Step 2: Verificar imports y tests existentes**

```bash
cd /data/agora && PYTHONPATH=/data/agora .venv/bin/python -c "
from backend.schemas.models import (TurnRequest, ProfileIn, ProfileOut, ProfilePatch, ChannelIn, ChannelOut, ChannelPatch, RosterAddIn, RosterPatch, RosterEntry)
print('OK')
" && .venv/bin/python -m pytest -q --tb=short
```

Esperado: `OK` + `15 passed`

- [ ] **Step 3: Commit**

```bash
git add backend/schemas/models.py
git commit -m "feat: Pydantic schemas for profiles, channels, roster"
```

---

## Task 5: Profiles API (TDD)

**Files:**
- Create: `backend/tests/test_profiles_api.py`
- Create: `backend/api/profiles.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Escribir los tests (fallarán)**

```python
# backend/tests/test_profiles_api.py
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


MOCK_PROFILE = {
    "id": 1,
    "name": "Platón",
    "tipo": "tertuliano",
    "model": "claude-sonnet-4-6",
    "temperature": 0.7,
    "color": "azul",
    "funcion": "Dialoga mediante mitos y alegorías",
    "system_prompt": "Eres Platón.",
    "archived": False,
    "created_at": datetime(2026, 6, 6, 10, 0, 0),
    "updated_at": datetime(2026, 6, 6, 10, 0, 0),
}


@pytest.mark.asyncio
async def test_create_profile():
    from backend.main import app

    with (
        patch("backend.api.profiles.insert_profile", AsyncMock(return_value=1)),
        patch("backend.api.profiles.get_profile", AsyncMock(return_value=MOCK_PROFILE)),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/profiles",
                json={"name": "Platón", "funcion": "Dialoga mediante mitos", "system_prompt": "Eres Platón."},
            )
    assert resp.status_code == 201
    assert resp.json()["id"] == 1
    assert resp.json()["name"] == "Platón"


@pytest.mark.asyncio
async def test_list_profiles():
    from backend.main import app

    with patch("backend.api.profiles.list_profiles", AsyncMock(return_value=[MOCK_PROFILE])):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/profiles")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["name"] == "Platón"


@pytest.mark.asyncio
async def test_get_profile():
    from backend.main import app

    with patch("backend.api.profiles.get_profile", AsyncMock(return_value=MOCK_PROFILE)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/profiles/1")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Platón"


@pytest.mark.asyncio
async def test_get_profile_not_found():
    from backend.main import app

    with patch("backend.api.profiles.get_profile", AsyncMock(return_value=None)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/profiles/999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_profile():
    from backend.main import app

    updated = {**MOCK_PROFILE, "color": "rojo"}
    with (
        patch("backend.api.profiles.get_profile", AsyncMock(side_effect=[MOCK_PROFILE, updated])),
        patch("backend.api.profiles.update_profile", AsyncMock()),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.patch("/profiles/1", json={"color": "rojo"})
    assert resp.status_code == 200
    assert resp.json()["color"] == "rojo"


@pytest.mark.asyncio
async def test_delete_profile():
    from backend.main import app

    with (
        patch("backend.api.profiles.get_profile", AsyncMock(return_value=MOCK_PROFILE)),
        patch("backend.api.profiles.archive_profile", AsyncMock()),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.delete("/profiles/1")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_profile_not_found():
    from backend.main import app

    with patch("backend.api.profiles.get_profile", AsyncMock(return_value=None)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.delete("/profiles/999")
    assert resp.status_code == 404
```

- [ ] **Step 2: Verificar que los tests fallan**

```bash
cd /data/agora && .venv/bin/python -m pytest backend/tests/test_profiles_api.py -v
```

Esperado: `ImportError` — `backend.api.profiles` no existe.

- [ ] **Step 3: Crear `backend/api/profiles.py`**

```python
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from backend.db.queries.profiles import (
    archive_profile,
    get_profile,
    insert_profile,
    list_profiles,
    update_profile,
)
from backend.schemas.models import ProfileIn, ProfileOut, ProfilePatch

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("", response_model=list[ProfileOut])
async def list_profiles_endpoint():
    return await list_profiles()


@router.post("", response_model=ProfileOut, status_code=201)
async def create_profile(body: ProfileIn):
    profile_id = await insert_profile(
        name=body.name,
        tipo=body.tipo,
        model=body.model,
        temperature=body.temperature,
        color=body.color,
        funcion=body.funcion,
        system_prompt=body.system_prompt,
    )
    return await get_profile(profile_id)


@router.get("/{profile_id}", response_model=ProfileOut)
async def get_profile_endpoint(profile_id: int):
    profile = await get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")
    return profile


@router.patch("/{profile_id}", response_model=ProfileOut)
async def patch_profile(profile_id: int, body: ProfilePatch):
    profile = await get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")
    fields = body.model_dump(exclude_none=True)
    await update_profile(profile_id, fields)
    return await get_profile(profile_id)


@router.delete("/{profile_id}", status_code=204)
async def delete_profile(profile_id: int):
    profile = await get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")
    await archive_profile(profile_id)
    return Response(status_code=204)
```

- [ ] **Step 4: Registrar el router en `backend/main.py`**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.api.profiles import router as profiles_router
from backend.api.stream import router as stream_router
from backend.db.connection import close_pool, init_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    yield
    await close_pool()


app = FastAPI(title="Agora API", version="0.1.0", lifespan=lifespan)
app.include_router(stream_router)
app.include_router(profiles_router)
```

- [ ] **Step 5: Verificar que los tests pasan**

```bash
cd /data/agora && .venv/bin/python -m pytest backend/tests/test_profiles_api.py -v
```

Esperado: `7 passed`.

- [ ] **Step 6: Suite completa**

```bash
cd /data/agora && .venv/bin/python -m pytest -q
```

Esperado: `22 passed` (15 anteriores + 7 nuevos).

- [ ] **Step 7: Commit**

```bash
git add backend/api/profiles.py backend/tests/test_profiles_api.py backend/main.py
git commit -m "feat: profiles REST API with soft-delete (TDD)"
```

---

## Task 6: Channels + Roster API (TDD)

**Files:**
- Create: `backend/tests/test_channels_api.py`
- Create: `backend/api/channels.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Escribir los tests (fallarán)**

```python
# backend/tests/test_channels_api.py
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


MOCK_CHANNEL = {
    "id": 1,
    "title": "Debate SaaS",
    "mode": "debate",
    "incognito": False,
    "created_at": datetime(2026, 6, 6, 10, 0, 0),
}
MOCK_ROSTER_ENTRY = {
    "profile_id": 1,
    "name": "Sócrates",
    "tipo": "tertuliano",
    "speaking_order": 0,
    "active": True,
}


@pytest.mark.asyncio
async def test_create_channel():
    from backend.main import app

    with (
        patch("backend.api.channels.insert_channel", AsyncMock(return_value=1)),
        patch("backend.api.channels.get_channel", AsyncMock(return_value=MOCK_CHANNEL)),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/channels", json={"title": "Debate SaaS"})
    assert resp.status_code == 201
    assert resp.json()["id"] == 1
    assert resp.json()["title"] == "Debate SaaS"


@pytest.mark.asyncio
async def test_list_channels():
    from backend.main import app

    with patch("backend.api.channels.list_channels", AsyncMock(return_value=[MOCK_CHANNEL])):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/channels")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_get_channel():
    from backend.main import app

    with patch("backend.api.channels.get_channel", AsyncMock(return_value=MOCK_CHANNEL)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/channels/1")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Debate SaaS"


@pytest.mark.asyncio
async def test_get_channel_not_found():
    from backend.main import app

    with patch("backend.api.channels.get_channel", AsyncMock(return_value=None)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/channels/999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_channel():
    from backend.main import app

    updated = {**MOCK_CHANNEL, "title": "Nuevo título"}
    with (
        patch("backend.api.channels.get_channel", AsyncMock(side_effect=[MOCK_CHANNEL, updated])),
        patch("backend.api.channels.update_channel", AsyncMock()),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.patch("/channels/1", json={"title": "Nuevo título"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "Nuevo título"


@pytest.mark.asyncio
async def test_list_roster():
    from backend.main import app

    with (
        patch("backend.api.channels.get_channel", AsyncMock(return_value=MOCK_CHANNEL)),
        patch("backend.api.channels.get_full_roster", AsyncMock(return_value=[MOCK_ROSTER_ENTRY])),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/channels/1/profiles")
    assert resp.status_code == 200
    assert resp.json()[0]["name"] == "Sócrates"


@pytest.mark.asyncio
async def test_add_to_roster():
    from backend.main import app

    with (
        patch("backend.api.channels.get_channel", AsyncMock(return_value=MOCK_CHANNEL)),
        patch("backend.api.channels.count_active_roster", AsyncMock(return_value=0)),
        patch("backend.api.channels.add_to_roster", AsyncMock()),
        patch("backend.api.channels.get_roster_entry", AsyncMock(return_value=MOCK_ROSTER_ENTRY)),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/channels/1/profiles", json={"profile_id": 1, "speaking_order": 0})
    assert resp.status_code == 201
    assert resp.json()["profile_id"] == 1
    assert resp.json()["name"] == "Sócrates"


@pytest.mark.asyncio
async def test_add_to_roster_limit_exceeded():
    from backend.main import app

    with (
        patch("backend.api.channels.get_channel", AsyncMock(return_value=MOCK_CHANNEL)),
        patch("backend.api.channels.count_active_roster", AsyncMock(return_value=3)),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/channels/1/profiles", json={"profile_id": 4, "speaking_order": 3})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_remove_from_roster():
    from backend.main import app

    with (
        patch("backend.api.channels.get_channel", AsyncMock(return_value=MOCK_CHANNEL)),
        patch("backend.api.channels.get_roster_entry", AsyncMock(return_value=MOCK_ROSTER_ENTRY)),
        patch("backend.api.channels.remove_from_roster", AsyncMock()),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.delete("/channels/1/profiles/1")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_patch_roster_entry():
    from backend.main import app

    updated = {**MOCK_ROSTER_ENTRY, "speaking_order": 1}
    with (
        patch("backend.api.channels.get_channel", AsyncMock(return_value=MOCK_CHANNEL)),
        patch("backend.api.channels.get_roster_entry", AsyncMock(side_effect=[MOCK_ROSTER_ENTRY, updated])),
        patch("backend.api.channels.update_roster_entry", AsyncMock()),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.patch("/channels/1/profiles/1", json={"speaking_order": 1})
    assert resp.status_code == 200
    assert resp.json()["speaking_order"] == 1
```

- [ ] **Step 2: Verificar que los tests fallan**

```bash
cd /data/agora && .venv/bin/python -m pytest backend/tests/test_channels_api.py -v
```

Esperado: `ImportError` — `backend.api.channels` no existe.

- [ ] **Step 3: Crear `backend/api/channels.py`**

```python
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from backend.db.queries.channels import (
    add_to_roster,
    count_active_roster,
    get_channel,
    get_full_roster,
    get_roster_entry,
    insert_channel,
    list_channels,
    remove_from_roster,
    update_channel,
    update_roster_entry,
)
from backend.schemas.models import (
    ChannelIn,
    ChannelOut,
    ChannelPatch,
    RosterAddIn,
    RosterEntry,
    RosterPatch,
)

router = APIRouter(prefix="/channels", tags=["channels"])


@router.get("", response_model=list[ChannelOut])
async def list_channels_endpoint():
    return await list_channels()


@router.post("", response_model=ChannelOut, status_code=201)
async def create_channel(body: ChannelIn):
    channel_id = await insert_channel(title=body.title, mode=body.mode, incognito=body.incognito)
    return await get_channel(channel_id)


@router.get("/{channel_id}", response_model=ChannelOut)
async def get_channel_endpoint(channel_id: int):
    channel = await get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")
    return channel


@router.patch("/{channel_id}", response_model=ChannelOut)
async def patch_channel(channel_id: int, body: ChannelPatch):
    channel = await get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")
    fields = body.model_dump(exclude_none=True)
    await update_channel(channel_id, fields)
    return await get_channel(channel_id)


@router.get("/{channel_id}/profiles", response_model=list[RosterEntry])
async def list_roster(channel_id: int):
    channel = await get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")
    return await get_full_roster(channel_id)


@router.post("/{channel_id}/profiles", response_model=RosterEntry, status_code=201)
async def add_profile_to_channel(channel_id: int, body: RosterAddIn):
    channel = await get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")
    active_count = await count_active_roster(channel_id)
    if active_count >= 3:
        raise HTTPException(status_code=400, detail="Channel already has 3 active profiles (maximum)")
    await add_to_roster(channel_id=channel_id, profile_id=body.profile_id, speaking_order=body.speaking_order)
    return await get_roster_entry(channel_id, body.profile_id)


@router.delete("/{channel_id}/profiles/{profile_id}", status_code=204)
async def remove_profile_from_channel(channel_id: int, profile_id: int):
    channel = await get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")
    entry = await get_roster_entry(channel_id, profile_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Profile {profile_id} not in channel {channel_id}")
    await remove_from_roster(channel_id, profile_id)
    return Response(status_code=204)


@router.patch("/{channel_id}/profiles/{profile_id}", response_model=RosterEntry)
async def patch_roster_entry(channel_id: int, profile_id: int, body: RosterPatch):
    channel = await get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")
    entry = await get_roster_entry(channel_id, profile_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Profile {profile_id} not in channel {channel_id}")
    fields = body.model_dump(exclude_none=True)
    await update_roster_entry(channel_id, profile_id, fields)
    return await get_roster_entry(channel_id, profile_id)
```

- [ ] **Step 4: Registrar el router en `backend/main.py`**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.api.channels import router as channels_router
from backend.api.profiles import router as profiles_router
from backend.api.stream import router as stream_router
from backend.db.connection import close_pool, init_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    yield
    await close_pool()


app = FastAPI(title="Agora API", version="0.1.0", lifespan=lifespan)
app.include_router(stream_router)
app.include_router(profiles_router)
app.include_router(channels_router)
```

- [ ] **Step 5: Verificar que los tests pasan**

```bash
cd /data/agora && .venv/bin/python -m pytest backend/tests/test_channels_api.py -v
```

Esperado: `10 passed`.

- [ ] **Step 6: Suite completa**

```bash
cd /data/agora && .venv/bin/python -m pytest -q
```

Esperado: `32 passed` (22 anteriores + 10 nuevos).

- [ ] **Step 7: Commit**

```bash
git add backend/api/channels.py backend/tests/test_channels_api.py backend/main.py
git commit -m "feat: channels and roster REST API with 3-profile guardrail (TDD)"
```

---

## Task 7: Orchestrator — TURN_COMPLETE JSON + logs + startup (TDD)

**Files:**
- Modify: `backend/services/orchestrator.py`
- Modify: `backend/tests/test_orchestrator.py`
- Modify: `backend/tests/test_stream.py`
- Modify: `backend/main.py`

Este task cambia el TURN_COMPLETE de string literal a JSON, añade `total_cost_usd`, y agrega logging. La estrategia TDD: primero actualizar los tests para que fallen con el formato antiguo, luego actualizar el orchestrator.

- [ ] **Step 1: Actualizar `backend/tests/test_orchestrator.py`**

Reemplazar el fichero completo:

```python
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
        patch("backend.services.orchestrator.insert_message", AsyncMock(return_value=42)),
        patch("backend.services.orchestrator.get_channel", AsyncMock(return_value=MOCK_CHANNEL)),
        patch("backend.services.orchestrator.get_active_roster", AsyncMock(return_value=MOCK_ROSTER)),
        patch("backend.services.orchestrator.get_latest_summary", AsyncMock(return_value=None)),
        patch("backend.services.orchestrator.get_context_messages", AsyncMock(return_value=[])),
        patch("backend.services.orchestrator.stream_turn", _mock_stream_turn),
        patch("backend.services.orchestrator.get_total_cost_usd", AsyncMock(return_value=Decimal("0.000010"))),
    ):
        chunks = []
        async for chunk in run_turn(1, "¿SaaS?"):
            chunks.append(chunk)

    # Parse all SSE events
    events = [json.loads(c.removeprefix("data: ").strip()) for c in chunks if c.startswith("data:")]
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
        patch("backend.services.orchestrator.insert_message", insert_mock),
        patch("backend.services.orchestrator.get_channel", AsyncMock(return_value=MOCK_CHANNEL)),
        patch("backend.services.orchestrator.get_active_roster", AsyncMock(return_value=MOCK_ROSTER)),
        patch("backend.services.orchestrator.get_latest_summary", AsyncMock(return_value=None)),
        patch("backend.services.orchestrator.get_context_messages", AsyncMock(return_value=[])),
        patch("backend.services.orchestrator.stream_turn", _mock_stream_turn),
        patch("backend.services.orchestrator.get_total_cost_usd", AsyncMock(return_value=Decimal("0"))),
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
        patch("backend.services.orchestrator.insert_message", AsyncMock(return_value=1)),
        patch("backend.services.orchestrator.get_channel", AsyncMock(return_value=MOCK_CHANNEL)),
        patch("backend.services.orchestrator.get_active_roster", AsyncMock(return_value=[])),
        patch("backend.services.orchestrator.get_total_cost_usd", AsyncMock(return_value=Decimal("0"))),
    ):
        chunks = []
        async for chunk in run_turn(1, "Hola"):
            chunks.append(chunk)

    assert len(chunks) == 1
    event = json.loads(chunks[0].removeprefix("data: ").strip())
    assert event["type"] == "TURN_COMPLETE"
    assert event["total_cost_usd"] == "0"
```

- [ ] **Step 2: Actualizar `backend/tests/test_stream.py` — mock TURN_COMPLETE**

Cambiar la línea 12 de `test_stream.py`:

```python
# ANTES:
yield "data: [TURN_COMPLETE]\n\n"

# DESPUÉS (reemplaza solo esa línea):
yield f"data: {json.dumps({'type': 'TURN_COMPLETE', 'total_cost_usd': '0.000009'}, ensure_ascii=False)}\n\n"
```

El fichero completo queda:

```python
import json

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import patch, AsyncMock


async def _mock_run_turn(channel_id: int, human_content: str):
    yield f"data: {json.dumps({'type': 'start', 'profile_id': 1, 'profile_name': 'Sócrates'}, ensure_ascii=False)}\n\n"
    yield f"data: {json.dumps({'type': 'token', 'profile_id': 1, 'token': 'Hola'}, ensure_ascii=False)}\n\n"
    yield f"data: {json.dumps({'type': 'done', 'profile_id': 1, 'profile_name': 'Sócrates', 'tokens_in': 5, 'tokens_out': 3, 'cost_usd': '0.000009'}, ensure_ascii=False)}\n\n"
    yield f"data: {json.dumps({'type': 'TURN_COMPLETE', 'total_cost_usd': '0.000009'}, ensure_ascii=False)}\n\n"


MOCK_CHANNEL = {"id": 1, "title": "Test", "mode": "debate", "incognito": False}


@pytest.mark.asyncio
async def test_post_message_streams_sse():
    from backend.main import app

    with (
        patch("backend.api.stream.get_channel", AsyncMock(return_value=MOCK_CHANNEL)),
        patch("backend.api.stream.run_turn", _mock_run_turn),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            async with ac.stream(
                "POST", "/channels/1/messages", json={"content": "¿SaaS?"}
            ) as resp:
                assert resp.status_code == 200
                assert "text/event-stream" in resp.headers["content-type"]
                body = ""
                async for chunk in resp.aiter_text():
                    body += chunk

    assert "Sócrates" in body
    assert "Hola" in body
    assert "TURN_COMPLETE" in body


@pytest.mark.asyncio
async def test_post_message_404_unknown_channel():
    from backend.main import app

    with patch("backend.api.stream.get_channel", AsyncMock(return_value=None)):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.post("/channels/999/messages", json={"content": "hola"})
    assert resp.status_code == 404
```

- [ ] **Step 3: Verificar que los tests orquestador FALLAN con el orchestrator antiguo**

```bash
cd /data/agora && .venv/bin/python -m pytest backend/tests/test_orchestrator.py -v
```

Esperado: al menos 2 tests FAIL (los que verifican TURN_COMPLETE JSON).

- [ ] **Step 4: Reemplazar `backend/services/orchestrator.py`**

```python
import json
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


async def run_turn(channel_id: int, human_content: str) -> AsyncGenerator[str, None]:
    await insert_message(channel_id=channel_id, role="human", content=human_content)

    channel = await get_channel(channel_id)
    roster = await get_active_roster(channel_id)
    profile_names: dict[int, str] = {p["id"]: p["name"] for p in roster}

    logger.info("turn started channel_id={} profiles={}", channel_id, [p["name"] for p in roster])

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

        try:
            async for chunk in stream_turn(system, api_messages, profile["model"], profile["temperature"]):
                if isinstance(chunk, str):
                    full_text.append(chunk)
                    yield f"data: {json.dumps({'type': 'token', 'profile_id': profile['id'], 'token': chunk}, ensure_ascii=False)}\n\n"
                else:
                    usage = chunk
        except Exception as exc:
            logger.error("stream error channel_id={} profile={}: {}", channel_id, profile["name"], exc)
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

- [ ] **Step 5: Añadir startup log en `backend/main.py`**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.api.channels import router as channels_router
from backend.api.profiles import router as profiles_router
from backend.api.stream import router as stream_router
from backend.db.connection import close_pool, init_pool
from backend.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    logger.info("startup: DB pool initialized")
    yield
    await close_pool()


app = FastAPI(title="Agora API", version="0.1.0", lifespan=lifespan)
app.include_router(stream_router)
app.include_router(profiles_router)
app.include_router(channels_router)
```

- [ ] **Step 6: Suite completa — todos pasan**

```bash
cd /data/agora && .venv/bin/python -m pytest -v
```

Esperado: `32 passed`.

- [ ] **Step 7: Commit**

```bash
git add backend/services/orchestrator.py backend/tests/test_orchestrator.py backend/tests/test_stream.py backend/main.py
git commit -m "feat: TURN_COMPLETE with total_cost_usd JSON + logging (TDD)"
```

---

## Task 8: Verificación end-to-end

*(Sin tests unitarios — es integración real con DB y API.)*

- [ ] **Step 1: Reiniciar uvicorn** (recargar config con los nuevos routers)

Ctrl+C en la terminal de uvicorn y volver a lanzar:

```bash
cd /data/agora && .venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8765 --reload
```

Esperado en log: `startup: DB pool initialized`

- [ ] **Step 2: Crear un segundo perfil — Platón**

```bash
curl -s -X POST http://localhost:8765/profiles \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Platón",
    "tipo": "tertuliano",
    "model": "claude-sonnet-4-6",
    "temperature": 0.7,
    "color": "dorado",
    "funcion": "Dialoga mediante mitos y alegorías",
    "system_prompt": "Eres Platón. Hablas con solemnidad y usas alegorías y mitos para ilustrar la verdad. Tu referencia es la alegoría de la caverna: la mayoría vive en un mundo de sombras y tú intentas guiar hacia la luz. Reaccionas a lo que dicen los demás elevando la conversación a sus implicaciones más profundas. Sé breve y contundente. Responde en español."
  }' | python3 -m json.tool
```

Esperado: JSON con `"id": 2` (o el siguiente id disponible).

- [ ] **Step 3: Añadir Platón al canal 1**

```bash
PLATON_ID=$(curl -s http://localhost:8765/profiles | python3 -c "import sys,json; profiles=json.load(sys.stdin); print(next(p['id'] for p in profiles if p['name']=='Platón'))")
echo "Platón id: $PLATON_ID"

curl -s -X POST http://localhost:8765/channels/1/profiles \
  -H "Content-Type: application/json" \
  -d "{\"profile_id\": $PLATON_ID, \"speaking_order\": 1}" | python3 -m json.tool
```

Esperado: JSON con `"profile_id": <id>`, `"name": "Platón"`, `"active": true`.

- [ ] **Step 4: Verificar el roster del canal 1**

```bash
curl -s http://localhost:8765/channels/1/profiles | python3 -m json.tool
```

Esperado: array con Sócrates (order 0) y Platón (order 1).

- [ ] **Step 5: Test multi-tertuliano en streaming**

```bash
curl -N -X POST http://localhost:8765/channels/1/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "¿La IA puede alcanzar la sabiduría?"}'
```

Esperado:
- Eventos `start`/`token`/`done` para Sócrates
- Eventos `start`/`token`/`done` para Platón
- Evento final `{"type": "TURN_COMPLETE", "total_cost_usd": "..."}` (con coste acumulado real)

- [ ] **Step 6: Verificar LogCentral**

```bash
tail -5 /data/agora/logs/tertulia.log | python3 -m json.tool
```

Esperado: líneas JSON con `"source": "tertulia"`, incluyendo `"turn started"` y `"turn done"`.

- [ ] **Step 7: Commit final**

```bash
cd /data/agora
git add .
git commit -m "feat: Fase 2A complete — CRUD API, multi-tertuliano, live cost, LogCentral"
```

---

## Notas

- **`update_profile` / `update_channel` / `update_roster_entry`** usan SQL dinámico con f-string en las claves. Las claves vienen siempre de `body.model_dump(exclude_none=True)` donde `body` es un modelo Pydantic — no hay SQL injection posible.
- **TURN_COMPLETE** cambia de string literal a JSON en este plan. Los clientes SSE deben detectarlo por `event["type"] == "TURN_COMPLETE"`, no por `[TURN_COMPLETE]` en el body.
- **Puerto**: sigue siendo 8765 (verificado libre en Task 8 de Fase 1). Actualizar `stack.md` antes de convertir en servicio systemd.
- **Próximo sub-proyecto**: Fase 2B — compresión de contexto (rolling summary con Haiku), @mención, "otra ronda".
