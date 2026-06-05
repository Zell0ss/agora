# Agora Fase 1 — Slice Vertical: Streaming SSE Funcionando

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un canal + un tertuliano + un turno → tokens de Claude llegando en tiempo real vía SSE. Verificado con `curl`.

**Architecture:** Layered FastAPI backend (api → services → db/queries). El camino feliz mínimo: `POST /channels/{id}/messages` guarda el mensaje humano, llama a la API de Anthropic en streaming, reenvía tokens como SSE al cliente, y persiste el mensaje de respuesta con coste. Sin CRUD de perfiles/canales en esta fase — el seed va en `init.sql`.

**Tech Stack:** FastAPI 0.115+, Python 3.11, aiomysql 0.2+, anthropic SDK 0.40+, pydantic-settings 2+, pytest + pytest-asyncio (auto mode), httpx para tests de endpoint.

---

## Mapa de ficheros

```
agora/
├── pyproject.toml                        # pytest config
├── backend/
│   ├── __init__.py
│   ├── main.py                           # FastAPI app + lifespan (pool DB)
│   ├── config.py                         # Settings desde .env (pydantic-settings)
│   ├── requirements.txt
│   ├── db/
│   │   ├── __init__.py
│   │   ├── connection.py                 # Pool aiomysql + get_db() context manager
│   │   ├── init.sql                      # Schema completo + seed (1 perfil, 1 canal)
│   │   └── queries/
│   │       ├── __init__.py
│   │       ├── channels.py               # get_channel(), get_active_roster()
│   │       └── messages.py               # insert_message(), get_context_messages(), get_latest_summary()
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── models.py                     # Pydantic: TurnRequest, SSEChunk
│   ├── services/
│   │   ├── __init__.py
│   │   ├── andamio.py                    # build_context() → tuple[str, list[dict]]
│   │   ├── llm.py                        # stream_turn() → AsyncGenerator
│   │   └── orchestrator.py              # run_turn() → AsyncGenerator[str] (SSE strings)
│   ├── api/
│   │   ├── __init__.py
│   │   └── stream.py                     # Router: POST /channels/{id}/messages
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py
│       ├── test_andamio.py
│       ├── test_llm.py
│       ├── test_orchestrator.py
│       └── test_stream.py
```

**Contratos entre capas:**
- `andamio.build_context(profile: dict, channel: dict, messages: list[dict], profile_names: dict[int, str], summary: dict | None) → tuple[str, list[dict]]`
  - Devuelve `(system_prompt, [{"role": "user", "content": transcript}])`
- `llm.stream_turn(system: str, messages: list[dict], model: str, temperature: float) → AsyncGenerator`
  - Yields: `str` (token) hasta agotar, luego `dict` con `{tokens_in, tokens_out, cost_usd}`
- `orchestrator.run_turn(channel_id: int, human_content: str) → AsyncGenerator[str, None]`
  - Yields strings SSE-formateadas: `"data: {...}\n\n"`

---

## Task 1: Scaffold del proyecto

**Files:**
- Create: `pyproject.toml`
- Create: `backend/__init__.py`
- Create: `backend/requirements.txt`
- Create: `backend/config.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: todos los `__init__.py` de subdirectorios

- [ ] **Step 1: Crear estructura de directorios**

```bash
cd /data/agora
mkdir -p backend/db/queries backend/services backend/api backend/schemas backend/tests
touch backend/__init__.py
touch backend/db/__init__.py backend/db/queries/__init__.py
touch backend/services/__init__.py backend/api/__init__.py
touch backend/schemas/__init__.py backend/tests/__init__.py
```

- [ ] **Step 2: Crear `pyproject.toml` en la raíz**

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["backend/tests"]
```

- [ ] **Step 3: Crear `backend/requirements.txt`**

```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
anthropic>=0.40.0
aiomysql>=0.2.0
pydantic-settings>=2.0.0
pytest>=8.0.0
pytest-asyncio>=0.24.0
httpx>=0.27.0
```

- [ ] **Step 4: Instalar dependencias en el venv existente**

```bash
cd /data/agora
.venv/bin/pip install -r backend/requirements.txt -q
```

Verificar: `.venv/bin/python -c "import fastapi, anthropic, aiomysql; print('OK')"` → `OK`

- [ ] **Step 5: Crear `backend/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    anthropic_api_key: str
    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str
    db_password: str
    db_name: str = "tertulia_db"


settings = Settings()
```

- [ ] **Step 6: Crear `backend/tests/conftest.py`**

```python
import pytest
```

(pytest-asyncio en modo auto no necesita fixtures adicionales en Fase 1.)

- [ ] **Step 7: Verificar que pytest arranca**

```bash
cd /data/agora
.venv/bin/python -m pytest --collect-only
```

Esperado: `no tests ran` (0 errores de importación).

- [ ] **Step 8: Actualizar `.env` si `DB_NAME` no es `tertulia_db`**

```bash
grep DB_NAME /data/agora/.env
```

Si dice `agora_db`, corregirlo:

```bash
sed -i 's/DB_NAME=agora_db/DB_NAME=tertulia_db/' /data/agora/.env
```

- [ ] **Step 9: Commit**

```bash
cd /data/agora
git add pyproject.toml backend/
git commit -m "feat: scaffold backend structure and requirements"
```

---

## Task 2: Schema DB + pool de conexión

**Files:**
- Create: `backend/db/init.sql`
- Create: `backend/db/connection.py`

- [ ] **Step 1: Crear `backend/db/init.sql`**

```sql
-- tertulia_db schema v0
-- Ejecutar: mariadb -u josem -p tertulia_db < backend/db/init.sql

CREATE TABLE IF NOT EXISTS profiles (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  name          VARCHAR(80)  NOT NULL,
  tipo          ENUM('tertuliano','facilitador') NOT NULL DEFAULT 'tertuliano',
  model         VARCHAR(60)  NOT NULL,
  temperature   DECIMAL(2,1) NOT NULL DEFAULT 0.7,
  color         VARCHAR(30)  NULL,
  funcion       VARCHAR(255) NOT NULL,
  system_prompt MEDIUMTEXT   NOT NULL,
  archived      BOOLEAN      NOT NULL DEFAULT FALSE,
  created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS channels (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  title       VARCHAR(160) NOT NULL,
  mode        ENUM('debate','critica') NOT NULL DEFAULT 'debate',
  incognito   BOOLEAN      NOT NULL DEFAULT FALSE,
  created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS channel_profiles (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  channel_id     INT NOT NULL,
  profile_id     INT NOT NULL,
  speaking_order INT NOT NULL DEFAULT 0,
  active         BOOLEAN NOT NULL DEFAULT TRUE,
  joined_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_channel_profile (channel_id, profile_id),
  FOREIGN KEY (channel_id) REFERENCES channels(id)  ON DELETE CASCADE,
  FOREIGN KEY (profile_id) REFERENCES profiles(id)  ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS messages (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  channel_id  INT NOT NULL,
  role        ENUM('human','persona','system') NOT NULL,
  profile_id  INT NULL,
  content     MEDIUMTEXT NOT NULL,
  tokens_in   INT NULL,
  tokens_out  INT NULL,
  cost_usd    DECIMAL(10,6) NULL,
  created_at  TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  KEY idx_channel_time (channel_id, created_at),
  FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE,
  FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS summaries (
  id                  INT AUTO_INCREMENT PRIMARY KEY,
  channel_id          INT NOT NULL,
  content             MEDIUMTEXT NOT NULL,
  covers_up_to_msg_id BIGINT NOT NULL,
  created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_channel (channel_id, created_at),
  FOREIGN KEY (channel_id)          REFERENCES channels(id) ON DELETE CASCADE,
  FOREIGN KEY (covers_up_to_msg_id) REFERENCES messages(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Seed: 1 perfil (Sócrates) + 1 canal de prueba
INSERT IGNORE INTO profiles (id, name, tipo, model, temperature, color, funcion, system_prompt)
VALUES (
  1, 'Sócrates', 'tertuliano', 'claude-sonnet-4-6', 0.7, 'gris mármol',
  'Desnuda supuestos, hace pensar',
  'Eres Sócrates. No afirmas: preguntas. Tu herramienta es la mayéutica: sacar a la luz lo que los demás (y Josem) creen saber pero no han examinado.\n\n- No das soluciones ni opiniones propias. Devuelves la pregunta que desnuda el supuesto oculto.\n- Persigues las palabras vagas: "¿qué entiendes exactamente por ''mejor'', ''escalable'', ''sencillo''?". No dejas pasar un término sin definir.\n- Cuando alguien afirma algo con seguridad, buscas el caso que lo rompe: "¿y si...?".\n- Una buena pregunta tuya hace que el otro se detenga a pensar. Ese es tu éxito.\n- Eres incómodo, pero nunca cínico: preguntas porque crees que la idea merece ser pensada de verdad.'
);

INSERT IGNORE INTO channels (id, title, mode)
VALUES (1, 'Canal de prueba', 'debate');

INSERT IGNORE INTO channel_profiles (channel_id, profile_id, speaking_order)
VALUES (1, 1, 0);
```

- [ ] **Step 2: Crear la base de datos y ejecutar el schema**

```bash
mariadb -u josem -p -e "CREATE DATABASE IF NOT EXISTS tertulia_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mariadb -u josem -p tertulia_db < backend/db/init.sql
```

Verificar:

```bash
mariadb -u josem -p tertulia_db -e "SELECT id, name, model FROM profiles;"
```

Esperado: fila con `Sócrates` / `claude-sonnet-4-6`.

- [ ] **Step 3: Crear `backend/db/connection.py`**

```python
from contextlib import asynccontextmanager

import aiomysql

from backend.config import settings

_pool: aiomysql.Pool | None = None


async def init_pool() -> None:
    global _pool
    _pool = await aiomysql.create_pool(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        db=settings.db_name,
        autocommit=True,
        charset="utf8mb4",
        minsize=1,
        maxsize=10,
    )


async def close_pool() -> None:
    global _pool
    if _pool:
        _pool.close()
        await _pool.wait_closed()
        _pool = None


@asynccontextmanager
async def get_db():
    assert _pool is not None, "Pool not initialized — call init_pool() first"
    async with _pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            yield cur
```

- [ ] **Step 4: Commit**

```bash
git add backend/db/
git commit -m "feat: db schema, seed data, and connection pool"
```

---

## Task 3: Queries de DB (channels y messages)

**Files:**
- Create: `backend/db/queries/channels.py`
- Create: `backend/db/queries/messages.py`

*(Las queries de DB requieren conexión real — se verifican con un script de smoke test, no con mocks.)*

- [ ] **Step 1: Crear `backend/db/queries/channels.py`**

```python
from backend.db.connection import get_db


async def get_channel(channel_id: int) -> dict | None:
    async with get_db() as cur:
        await cur.execute("SELECT * FROM channels WHERE id = %s", (channel_id,))
        return await cur.fetchone()


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
```

- [ ] **Step 2: Crear `backend/db/queries/messages.py`**

```python
from decimal import Decimal

from backend.db.connection import get_db


async def insert_message(
    channel_id: int,
    role: str,
    content: str,
    profile_id: int | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    cost_usd: Decimal | None = None,
) -> int:
    async with get_db() as cur:
        await cur.execute(
            """
            INSERT INTO messages
              (channel_id, role, profile_id, content, tokens_in, tokens_out, cost_usd)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (channel_id, role, profile_id, content, tokens_in, tokens_out, cost_usd),
        )
        return cur.lastrowid


async def get_context_messages(
    channel_id: int,
    after_msg_id: int | None = None,
) -> list[dict]:
    async with get_db() as cur:
        if after_msg_id is not None:
            await cur.execute(
                """
                SELECT * FROM messages
                WHERE channel_id = %s AND id > %s
                ORDER BY created_at
                """,
                (channel_id, after_msg_id),
            )
        else:
            await cur.execute(
                "SELECT * FROM messages WHERE channel_id = %s ORDER BY created_at",
                (channel_id,),
            )
        return await cur.fetchall()


async def get_latest_summary(channel_id: int) -> dict | None:
    async with get_db() as cur:
        await cur.execute(
            """
            SELECT * FROM summaries
            WHERE channel_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (channel_id,),
        )
        return await cur.fetchone()
```

- [ ] **Step 3: Smoke test de las queries con la DB real**

Crear y ejecutar `/tmp/smoke_queries.py` (borrar después):

```python
import asyncio
from backend.db.connection import init_pool, close_pool
from backend.db.queries.channels import get_channel, get_active_roster
from backend.db.queries.messages import insert_message, get_context_messages

async def main():
    await init_pool()

    channel = await get_channel(1)
    assert channel is not None, "Canal 1 no encontrado — ejecuta init.sql primero"
    print(f"Canal: {channel['title']}")

    roster = await get_active_roster(1)
    assert len(roster) > 0, "Roster vacío"
    print(f"Tertulianos: {[p['name'] for p in roster]}")

    msg_id = await insert_message(channel_id=1, role="human", content="Test smoke")
    assert isinstance(msg_id, int) and msg_id > 0
    print(f"Mensaje insertado: id={msg_id}")

    msgs = await get_context_messages(1)
    assert any(m["id"] == msg_id for m in msgs)
    print(f"Mensajes en canal: {len(msgs)}")

    await close_pool()
    print("Smoke test OK")

asyncio.run(main())
```

```bash
cd /data/agora && PYTHONPATH=/data/agora .venv/bin/python /tmp/smoke_queries.py
```

Esperado:
```
Canal: Canal de prueba
Tertulianos: ['Sócrates']
Mensaje insertado: id=1
Mensajes en canal: 1
Smoke test OK
```

Borrar el mensaje de prueba y el script:

```bash
mariadb -u josem -p tertulia_db -e "DELETE FROM messages WHERE content = 'Test smoke';"
rm /tmp/smoke_queries.py
```

- [ ] **Step 4: Commit**

```bash
git add backend/db/queries/
git commit -m "feat: db queries for channels and messages (slice)"
```

---

## Task 4: Andamio — `build_context()` (TDD)

**Files:**
- Create: `backend/tests/test_andamio.py`
- Create: `backend/services/andamio.py`

- [ ] **Step 1: Escribir los tests (fallarán)**

```python
# backend/tests/test_andamio.py
import pytest
from backend.services.andamio import build_context


def _profile(tipo: str = "tertuliano", system_prompt: str = "Eres Sócrates.") -> dict:
    return {
        "id": 1,
        "name": "Sócrates",
        "tipo": tipo,
        "system_prompt": system_prompt,
    }


def _channel(mode: str = "debate") -> dict:
    return {"id": 1, "mode": mode}


def test_tertuliano_debate_includes_andamio():
    system, msgs = build_context(_profile(), _channel("debate"), [], {})
    assert "tertulia" in system
    assert "Eres Sócrates." in system
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"


def test_facilitador_no_andamio():
    system, msgs = build_context(_profile("facilitador", "Eres RUIZ."), _channel(), [], {})
    assert system == "Eres RUIZ."
    assert "tertulia" not in system


def test_tertuliano_critica_includes_andamio_critica():
    system, _ = build_context(_profile(), _channel("critica"), [], {})
    assert "texto" in system.lower() or "crítica" in system.lower()
    assert "Eres Sócrates." in system


def test_transcript_labels_human_as_josem():
    messages = [{"role": "human", "profile_id": None, "content": "¿SaaS?"}]
    _, msgs = build_context(_profile(), _channel(), messages, {})
    assert "Josem: ¿SaaS?" in msgs[0]["content"]


def test_transcript_labels_persona_by_name():
    messages = [{"role": "persona", "profile_id": 1, "content": "Buena pregunta"}]
    _, msgs = build_context(_profile(), _channel(), messages, {1: "Sócrates"})
    assert "Sócrates: Buena pregunta" in msgs[0]["content"]


def test_transcript_skips_system_role():
    messages = [
        {"role": "system", "profile_id": None, "content": "Ignorar"},
        {"role": "human", "profile_id": None, "content": "Hola"},
    ]
    _, msgs = build_context(_profile(), _channel(), messages, {})
    assert "Ignorar" not in msgs[0]["content"]
    assert "Josem: Hola" in msgs[0]["content"]


def test_summary_prepended_to_transcript():
    summary = {"content": "Resumen anterior aquí."}
    messages = [{"role": "human", "profile_id": None, "content": "¿Y ahora?"}]
    _, msgs = build_context(_profile(), _channel(), messages, {}, summary=summary)
    content = msgs[0]["content"]
    assert content.index("Resumen anterior aquí.") < content.index("Josem:")


def test_empty_messages_returns_empty_transcript():
    _, msgs = build_context(_profile(), _channel(), [], {})
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == ""
```

- [ ] **Step 2: Verificar que los tests fallan**

```bash
cd /data/agora && .venv/bin/python -m pytest backend/tests/test_andamio.py -v
```

Esperado: `ImportError` o todos `FAILED` — `build_context` no existe aún.

- [ ] **Step 3: Implementar `backend/services/andamio.py`**

```python
ANDAMIO_DEBATE = (
    "Estás en una tertulia: una conversación de grupo con otros participantes "
    "(humanos e IA), cada uno con su propia voz. Verás el historial etiquetado "
    'por hablante (p. ej. "Josem:", "Sócrates:", "Tío Gilito:").\n\n'
    "Reglas de la tertulia:\n"
    "- Eres un participante, no un asistente. No estás aquí para complacer ni "
    "para dar la razón. Tu trabajo es aportar TU perspectiva, fiel a quién eres.\n"
    "- Lee lo que han dicho los demás y reacciona a ello nombrándolos: apoya, "
    "mata, matiza o lleva la idea en otra dirección. No repitas lo que ya se ha dicho.\n"
    "- Discrepa cuando discrepes. Busca el punto débil de las ideas, incluidas "
    "las de Josem. La cortesía vacía no ayuda a nadie; el desacuerdo bien argumentado sí.\n"
    "- Cuando notes que dos posturas chocan, o que hay algo que nadie ha nombrado "
    "del todo, dilo. Esa tensión suele ser donde está lo interesante.\n"
    "- Sé breve y punzante. Esto es una conversación rápida, no un ensayo: un par "
    "de párrafos como mucho. Si solo tienes una frase afilada, suéltala.\n"
    "- Mantente fiel a tu papel. No te conviertas en un Claude genérico y "
    "equilibrado: tu valor está precisamente en tu sesgo.\n"
    "- Responde en español."
)

ANDAMIO_CRITICA = (
    "Estás en una tertulia de crítica literaria. El usuario ha compartido un "
    "fragmento de texto para que lo analices junto con otros participantes.\n\n"
    "Reglas:\n"
    "- Tu objeto es el texto, no una idea abstracta. Habla de lo que está en la página.\n"
    "- Discrepa con los otros críticos si ves algo diferente. El desacuerdo "
    "bien argumentado mejora el texto.\n"
    "- Sé concreto: cita el fragmento, señala qué falla o qué funciona y por qué.\n"
    "- Sé breve y punzante. Un par de párrafos como mucho.\n"
    "- Mantente fiel a tu rol y tu sesgo: tu valor está en tu perspectiva particular.\n"
    "- Responde en español."
)


def build_context(
    profile: dict,
    channel: dict,
    messages: list[dict],
    profile_names: dict[int, str],
    summary: dict | None = None,
) -> tuple[str, list[dict]]:
    """
    Returns (system_prompt, api_messages) for the Anthropic API call.

    Matrix (from agora-disenio-decisiones.md §6):
      tertuliano + debate  → ANDAMIO_DEBATE + system_prompt
      tertuliano + critica → ANDAMIO_CRITICA + system_prompt
      facilitador          → system_prompt only (no scaffold)
    """
    if profile["tipo"] == "facilitador":
        system = profile["system_prompt"]
    elif channel["mode"] == "critica":
        system = ANDAMIO_CRITICA + "\n\n" + profile["system_prompt"]
    else:
        system = ANDAMIO_DEBATE + "\n\n" + profile["system_prompt"]

    lines: list[str] = []

    if summary:
        lines.append(f"[Resumen de la conversación anterior]\n{summary['content']}\n[Fin del resumen]")

    for msg in messages:
        if msg["role"] == "human":
            lines.append(f"Josem: {msg['content']}")
        elif msg["role"] == "persona" and msg.get("profile_id") is not None:
            name = profile_names.get(msg["profile_id"], f"Participante {msg['profile_id']}")
            lines.append(f"{name}: {msg['content']}")
        # role == "system" → skip

    transcript = "\n".join(lines)
    return system, [{"role": "user", "content": transcript}]
```

- [ ] **Step 4: Verificar que los tests pasan**

```bash
cd /data/agora && .venv/bin/python -m pytest backend/tests/test_andamio.py -v
```

Esperado: `8 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/services/andamio.py backend/tests/test_andamio.py
git commit -m "feat: andamio build_context with full matrix logic (TDD)"
```

---

## Task 5: LLM streaming — `stream_turn()` (TDD)

**Files:**
- Create: `backend/tests/test_llm.py`
- Create: `backend/services/llm.py`

- [ ] **Step 1: Escribir los tests (fallarán)**

```python
# backend/tests/test_llm.py
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
        async for chunk in stream_turn("s", [{"role": "user", "content": "x"}], "unknown-model", 0.5):
            chunks.append(chunk)

    usage = chunks[-1]
    assert usage["cost_usd"] == Decimal("0")
```

- [ ] **Step 2: Verificar que los tests fallan**

```bash
cd /data/agora && .venv/bin/python -m pytest backend/tests/test_llm.py -v
```

Esperado: `ImportError` o `FAILED`.

- [ ] **Step 3: Implementar `backend/services/llm.py`**

```python
from collections.abc import AsyncGenerator
from decimal import Decimal

import anthropic

from backend.config import settings

client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

# Precios por token (input/output) en USD. Verificar al actualizar modelos.
_COST_PER_TOKEN: dict[str, dict[str, float]] = {
    "claude-haiku-4-5-20251001": {"in": 0.8e-6, "out": 4e-6},
    "claude-sonnet-4-6":         {"in": 3e-6,   "out": 15e-6},
    "claude-opus-4-8":           {"in": 15e-6,  "out": 75e-6},
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
        temperature=temperature,
    ) as stream:
        async for text in stream.text_stream:
            yield text

        final = await stream.get_final_message()
        tokens_in = final.usage.input_tokens
        tokens_out = final.usage.output_tokens
        prices = _COST_PER_TOKEN.get(model, {"in": 0.0, "out": 0.0})
        cost = Decimal(str(round(tokens_in * prices["in"] + tokens_out * prices["out"], 8)))
        yield {"tokens_in": tokens_in, "tokens_out": tokens_out, "cost_usd": cost}
```

- [ ] **Step 4: Verificar que los tests pasan**

```bash
cd /data/agora && .venv/bin/python -m pytest backend/tests/test_llm.py -v
```

Esperado: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/services/llm.py backend/tests/test_llm.py
git commit -m "feat: Anthropic streaming client with token cost tracking (TDD)"
```

---

## Task 6: Orquestador — `run_turn()` (TDD)

**Files:**
- Create: `backend/tests/test_orchestrator.py`
- Create: `backend/services/orchestrator.py`

- [ ] **Step 1: Escribir los tests (fallarán)**

```python
# backend/tests/test_orchestrator.py
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
        "id": 1, "name": "Sócrates", "tipo": "tertuliano",
        "model": "claude-sonnet-4-6", "temperature": 0.7,
        "system_prompt": "Eres Sócrates.", "speaking_order": 0,
        "archived": False, "color": "gris",
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
    ):
        chunks = []
        async for chunk in run_turn(1, "¿SaaS?"):
            chunks.append(chunk)

    # SSE strings: parse each
    events = [json.loads(c.removeprefix("data: ").strip()) for c in chunks if c.startswith("data:") and "[TURN_COMPLETE]" not in c]
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
        patch("backend.services.orchestrator.get_channel", AsyncMock(return_value=MOCK_CHANNEL)),
        patch("backend.services.orchestrator.get_active_roster", AsyncMock(return_value=MOCK_ROSTER)),
        patch("backend.services.orchestrator.get_latest_summary", AsyncMock(return_value=None)),
        patch("backend.services.orchestrator.get_context_messages", AsyncMock(return_value=[])),
        patch("backend.services.orchestrator.stream_turn", _mock_stream_turn),
    ):
        async for _ in run_turn(1, "Hola"):
            pass

    first_call = insert_mock.call_args_list[0]
    assert first_call.kwargs["role"] == "human"
    assert first_call.kwargs["content"] == "Hola"
```

- [ ] **Step 2: Verificar que los tests fallan**

```bash
cd /data/agora && .venv/bin/python -m pytest backend/tests/test_orchestrator.py -v
```

Esperado: `ImportError` o `FAILED`.

- [ ] **Step 3: Implementar `backend/services/orchestrator.py`**

```python
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

        yield f"data: {json.dumps({'type': 'start', 'profile_id': profile['id'], 'profile_name': profile['name']})}\n\n"

        full_text: list[str] = []
        usage: dict | None = None

        async for chunk in stream_turn(system, api_messages, profile["model"], profile["temperature"]):
            if isinstance(chunk, str):
                full_text.append(chunk)
                yield f"data: {json.dumps({'type': 'token', 'profile_id': profile['id'], 'token': chunk})}\n\n"
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

        yield f"data: {json.dumps({'type': 'done', 'profile_id': profile['id'], 'profile_name': profile['name'], 'tokens_in': usage['tokens_in'] if usage else None, 'tokens_out': usage['tokens_out'] if usage else None, 'cost_usd': str(usage['cost_usd']) if usage else None})}\n\n"

    yield "data: [TURN_COMPLETE]\n\n"
```

- [ ] **Step 4: Verificar que los tests pasan**

```bash
cd /data/agora && .venv/bin/python -m pytest backend/tests/test_orchestrator.py -v
```

Esperado: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/services/orchestrator.py backend/tests/test_orchestrator.py
git commit -m "feat: turn orchestrator with SSE streaming (TDD)"
```

---

## Task 7: Schemas, endpoint SSE y app FastAPI (TDD)

**Files:**
- Create: `backend/schemas/models.py`
- Create: `backend/tests/test_stream.py`
- Create: `backend/api/stream.py`
- Create: `backend/main.py`

- [ ] **Step 1: Crear `backend/schemas/models.py`**

```python
from pydantic import BaseModel


class TurnRequest(BaseModel):
    content: str
```

- [ ] **Step 2: Escribir los tests del endpoint (fallarán)**

```python
# backend/tests/test_stream.py
import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch


async def _mock_run_turn(channel_id: int, human_content: str):
    import json
    yield f"data: {json.dumps({'type': 'start', 'profile_id': 1, 'profile_name': 'Sócrates'})}\n\n"
    yield f"data: {json.dumps({'type': 'token', 'profile_id': 1, 'token': 'Hola'})}\n\n"
    yield f"data: {json.dumps({'type': 'done', 'profile_id': 1, 'profile_name': 'Sócrates', 'tokens_in': 5, 'tokens_out': 3, 'cost_usd': '0.000009'})}\n\n"
    yield "data: [TURN_COMPLETE]\n\n"


MOCK_CHANNEL = {"id": 1, "title": "Test", "mode": "debate", "incognito": False}


@pytest.mark.asyncio
async def test_post_message_streams_sse():
    from backend.main import app

    with (
        patch("backend.api.stream.get_channel", AsyncMock(return_value=MOCK_CHANNEL)),
        patch("backend.api.stream.run_turn", _mock_run_turn),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            async with ac.stream("POST", "/channels/1/messages", json={"content": "¿SaaS?"}) as resp:
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
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/channels/999/messages", json={"content": "hola"})
    assert resp.status_code == 404
```

- [ ] **Step 3: Verificar que los tests fallan**

```bash
cd /data/agora && .venv/bin/python -m pytest backend/tests/test_stream.py -v
```

Esperado: `ImportError` (ni `backend.api.stream` ni `backend.main` existen aún).

- [ ] **Step 4: Crear `backend/api/stream.py`**

```python
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.db.queries.channels import get_channel
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
```

- [ ] **Step 5: Crear `backend/main.py`**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.api.stream import router as stream_router
from backend.db.connection import close_pool, init_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    yield
    await close_pool()


app = FastAPI(title="Agora API", version="0.1.0", lifespan=lifespan)
app.include_router(stream_router)
```

- [ ] **Step 6: Verificar que los tests pasan**

```bash
cd /data/agora && .venv/bin/python -m pytest backend/tests/test_stream.py -v
```

Esperado: `2 passed`.

- [ ] **Step 7: Suite completa**

```bash
cd /data/agora && .venv/bin/python -m pytest -v
```

Esperado: `14 passed` (8 andamio + 2 llm + 2 orchestrator + 2 stream).

- [ ] **Step 8: Commit**

```bash
git add backend/schemas/ backend/api/ backend/main.py backend/tests/test_stream.py
git commit -m "feat: FastAPI app with SSE streaming endpoint (TDD)"
```

---

## Task 8: Verificación end-to-end con curl

*(Este task no tiene tests unitarios — es la prueba de integración real con DB y Anthropic API.)*

- [ ] **Step 1: Verificar que `ANTHROPIC_API_KEY` está en el env**

```bash
grep ANTHROPIC_API_KEY /data/agora/.env
```

Debe mostrar la clave real (no el placeholder `sk-ant-api...`).

- [ ] **Step 2: Arrancar uvicorn**

```bash
cd /data/agora
.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8765 --reload
```

*(Elige el puerto 8765 provisionalmente — verificar en `stack.md` que está libre en seb01 antes de fijarlo definitivamente.)*

Esperado en el log:
```
INFO:     Application startup complete.
```

- [ ] **Step 3: Test de canal 404 (en otra terminal)**

```bash
curl -s -X POST http://localhost:8765/channels/999/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "test"}' | python3 -m json.tool
```

Esperado: `{"detail": "Channel 999 not found"}`.

- [ ] **Step 4: Test de streaming real**

```bash
curl -N -X POST http://localhost:8765/channels/1/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "¿Debería lanzar esto como SaaS?"}'
```

Esperado: stream de SSE con tokens de Sócrates llegando en tiempo real. Ejemplo:
```
data: {"type": "start", "profile_id": 1, "profile_name": "Sócrates"}

data: {"type": "token", "profile_id": 1, "token": "¿"}

data: {"type": "token", "profile_id": 1, "token": "Qu"}
...
data: {"type": "done", "profile_id": 1, ..., "tokens_in": 234, "tokens_out": 87, "cost_usd": "0.001986"}

data: [TURN_COMPLETE]
```

- [ ] **Step 5: Verificar persistencia en DB**

```bash
mariadb -u josem -p tertulia_db -e "
  SELECT id, role, profile_id, LEFT(content, 60) AS content, tokens_in, tokens_out, cost_usd
  FROM messages ORDER BY id DESC LIMIT 5;"
```

Esperado: filas con el mensaje humano (`role=human`) y la respuesta de Sócrates (`role=persona`) con `tokens_in`, `tokens_out`, `cost_usd` rellenos.

- [ ] **Step 6: Commit final**

```bash
cd /data/agora
git add .
git commit -m "feat: Fase 1 complete — SSE streaming with DB persistence verified"
```

---

## Notas finales

- **Puerto en producción:** El puerto 8765 es provisional. Antes de arrancar el servicio systemd, consultar `stack.md` para el mapa de puertos de seb01.
- **`DB_NAME`:** Verificar que `.env` tiene `DB_NAME=tertulia_db` (no `agora_db`).
- **Model strings:** Los strings de modelo en `init.sql` y `llm.py` deben coincidir con los vigentes en la API al momento de codear.
- **Fase 2:** CRUD completo, multi-tertuliano, compresión, @mención, etc. — plan separado.
