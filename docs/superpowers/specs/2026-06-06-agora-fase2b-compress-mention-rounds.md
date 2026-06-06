# Agora Fase 2B — Compresión de contexto, @mención y "Otra ronda"

## Goal

Añadir tres capacidades al orquestador de turnos:

1. **Compresión de contexto** — cuando el canal acumula ≥ 30 mensajes sin comprimir, Haiku resume el bloque más antiguo antes del turno.
2. **@mención** — el usuario puede forzar que hable un tertuliano concreto escribiendo `@Nombre`; matching exacto, case-insensitive y accent-insensitive.
3. **"Otra ronda"** — `POST /channels/{id}/rounds` repite el último turno humano sin guardar un nuevo mensaje.

---

## Architecture

El orquestador (`run_turn`) concentra las tres funciones: llama a `maybe_compress` antes de todo, parsea la @mención para filtrar el roster, y acepta un flag `save_human=False` para "otra ronda".

Un nuevo módulo `backend/services/compressor.py` aísla la lógica de compresión (consulta, llamada a Haiku, inserción de summary) para que pueda testearse sin tocar el orquestador.

**Flujo completo de un turno:**

```
POST /channels/{id}/messages  (save_human=True, default)
  1. maybe_compress(channel_id)
  2. insert_message(role="human")
  3. roster → parse_mention → speakers
  4. for profile in speakers: stream_turn(...)
  5. yield TURN_COMPLETE

POST /channels/{id}/rounds  (save_human=False)
  1. get_last_human_message → 400 si no hay ninguno
  2. run_turn(channel_id, content, save_human=False)
     → mismos pasos 1, 3, 4, 5
```

---

## Tech Stack

- Python 3.11, FastAPI, aiomysql, Anthropic SDK (`anthropic`)
- Haiku model: `claude-haiku-4-5-20251001`
- `unicodedata` (stdlib) para normalización de acentos

---

## Sección 1: Compresión de contexto

### Constante de umbral

```python
# backend/services/compressor.py
COMPRESSION_THRESHOLD = 30   # mensajes; cambiar sin tocar lógica
COMPRESSION_CHUNK = 20       # mensajes a comprimir por ronda
```

### DB — nuevas queries en `backend/db/queries/messages.py`

```python
async def count_messages_after(channel_id: int, after_msg_id: int | None) -> int:
    # after_msg_id=None → contar todos los mensajes del canal
    # after_msg_id=N    → contar mensajes con id > N

async def get_messages_chunk(
    channel_id: int, after_msg_id: int | None, limit: int
) -> list[dict]:
    # LEFT JOIN con profiles para obtener p.name como profile_name
    # Los `limit` mensajes más antiguos con id > after_msg_id (o desde el inicio si None)
    # Ordenados ASC por m.id
    # Cada row: id, role, profile_id, profile_name (NULL si human/system), content

async def get_last_human_message(channel_id: int) -> dict | None:
    # SELECT * FROM messages WHERE channel_id=%s AND role='human'
    # ORDER BY created_at DESC LIMIT 1
```

### DB — nueva query en `backend/db/queries/messages.py`

`get_latest_summary` ya existe en `messages.py` — no mover. Solo añadir `insert_summary`:

```python
async def insert_summary(
    channel_id: int, content: str, covers_up_to_msg_id: int
) -> int:
    # INSERT INTO summaries (channel_id, content, covers_up_to_msg_id) VALUES (...)
    # Retorna lastrowid
```

### Servicio — `backend/services/compressor.py` (archivo nuevo)

```python
from backend.db.queries.messages import (
    count_messages_after, get_messages_chunk, get_latest_summary, insert_summary
)
from anthropic import AsyncAnthropic

COMPRESSION_THRESHOLD = 30
COMPRESSION_CHUNK = 20
_HAIKU = "claude-haiku-4-5-20251001"

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
    # Llama a Haiku directamente (llamada de utilidad, sin personalidad)
    # Formatea los mensajes como transcript etiquetado y pide resumen neutral
    lines = [f"{m['profile_name'] or m['role']}: {m['content']}" for m in messages]
    transcript = "\n".join(lines)
    client = AsyncAnthropic()
    response = await client.messages.create(
        model=_HAIKU,
        max_tokens=512,
        system="Eres un compresor de transcripciones. Resume el siguiente fragmento de conversación de forma neutral, compacta y en tercera persona. Preserva los argumentos clave y las posiciones de cada hablante.",
        messages=[{"role": "user", "content": transcript}],
    )
    return response.content[0].text
```

**Nota:** `maybe_compress` es idempotente — si el umbral no se supera, no hace nada. Si hay un error en la llamada a Haiku, se propaga como excepción (el turno fallará con un error visible en lugar de silencioso).

---

## Sección 2: @mención

### Parser (en `backend/services/orchestrator.py`)

```python
import re
import unicodedata

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

### Integración en `run_turn`

```python
roster = await get_active_roster(channel_id)
if not roster:
    yield f"data: {json.dumps({'type': 'TURN_COMPLETE', 'total_cost_usd': '0'})}\n\n"
    return

mention = parse_mention(human_content, roster)
speakers = [mention] if mention else roster
# speakers es siempre una lista; si mention=None usa el roster completo (round-robin)
```

**Fallback:** si `@Nombre` no coincide con ningún tertuliano activo, se ignora y hablan todos (round-robin normal). Sin error, sin 400.

**Frontend (fuera de scope 2B, anotar para UI sprint):** autocomplete tipo WhatsApp con los nombres de los tertulianos activos del canal al escribir `@`.

---

## Sección 3: "Otra ronda"

### Modificación de `run_turn`

```python
async def run_turn(
    channel_id: int,
    human_content: str,
    save_human: bool = True,    # default True — no rompe nada existente
) -> AsyncGenerator[str, None]:
    await maybe_compress(channel_id)
    if save_human:
        await insert_message(channel_id=channel_id, role="human", content=human_content, ...)
    ...
```

### Nuevo endpoint en `backend/api/stream.py`

```python
from backend.db.queries.messages import get_last_human_message

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
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

**Comportamiento de error:** canal no existe → 404. Canal sin mensajes humanos → 400. El frontend debería deshabilitar el botón "otra ronda" hasta que exista al menos un turno, pero el backend protege igualmente.

---

## Testing

Cada pieza tiene tests unitarios con mocks:

- `test_compressor.py` — `maybe_compress` no comprime si count < threshold; comprime y llama `insert_summary` si count >= threshold
- `test_orchestrator.py` — `parse_mention` con y sin acento; `run_turn` con `save_human=False` no llama `insert_message`; `run_turn` filtra roster cuando hay @mención válida
- `test_stream.py` — `POST /channels/{id}/rounds` retorna 200 SSE; retorna 400 si no hay mensajes humanos; retorna 404 si canal no existe

---

## Guardarraíles (no hacer en 2B)

- ❌ Comprimir en background (race condition)
- ❌ Exponer endpoint de compresión manual
- ❌ Autocomplete @mención en backend (es trabajo de frontend)
- ❌ Comprimir todo de golpe si hay 100 mensajes — siempre en chunks de 20
