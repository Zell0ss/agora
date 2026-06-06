# Agora Fase 2A — CRUD + Coste en Vivo + LogCentral

**Fecha:** 2026-06-06
**Estado:** aprobado — listo para plan de implementación
**Sesión:** brainstorming Josem × Claude Code

---

## Contexto

Fase 1 entregó el slice vertical: un canal fijo (id=1, Sócrates) con streaming SSE funcionando y persistencia en DB. Fase 2A expande horizontalmente añadiendo la API REST para gestionar perfiles y canales, verificando que el orchestrator ya existente maneja múltiples tertulianos, exponiendo el coste acumulado por canal en el stream, e integrando LogCentral.

---

## Alcance exacto de Fase 2A

**Incluido:**
- CRUD REST de perfiles (`/profiles`)
- CRUD REST de canales (`/channels`)
- Gestión de roster como sub-recurso (`/channels/{id}/profiles`)
- `total_cost_usd` en el evento `TURN_COMPLETE` del SSE
- LogCentral (JSON sink loguru → `logs/tertulia.log`)

**Excluido de Fase 2A (queda para 2B y 2C):**
- Compresión de contexto (rolling summary)
- @mención
- "Otra ronda"
- Casting director
- Export Markdown
- Frontend

---

## 1. API Shape

### Perfiles

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/profiles` | Lista perfiles activos (`archived=false`) |
| POST | `/profiles` | Crea perfil |
| GET | `/profiles/{id}` | Obtiene un perfil (incluye archivados) |
| PATCH | `/profiles/{id}` | Edita en vivo (sobrescribe campos enviados) |
| DELETE | `/profiles/{id}` | Soft-delete: `archived=true` |

Borrado físico prohibido — la FK `ON DELETE RESTRICT` en `channel_profiles` lo impide de todas formas. El DELETE devuelve 204.

### Canales

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/channels` | Lista todos los canales |
| POST | `/channels` | Crea canal |
| GET | `/channels/{id}` | Obtiene un canal |
| PATCH | `/channels/{id}` | Edita título, mode o incognito |

### Roster (sub-recurso de canal)

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/channels/{id}/profiles` | Lista roster activo ordenado por `speaking_order` |
| POST | `/channels/{id}/profiles` | Añade perfil al canal |
| DELETE | `/channels/{id}/profiles/{profile_id}` | Desactiva (`active=false`), no borra físico |
| PATCH | `/channels/{id}/profiles/{profile_id}` | Actualiza `speaking_order` o `active` |

El roster admite hasta 3 tertulianos activos por canal (guardarraíl de MVP — validar en el POST).

---

## 2. Schemas Pydantic

```python
# Profiles
class ProfileIn(BaseModel):
    name: str
    tipo: Literal["tertuliano", "facilitador"] = "tertuliano"
    model: str = "claude-sonnet-4-6"
    temperature: float = 0.7
    color: str | None = None
    funcion: str
    system_prompt: str

class ProfileOut(ProfileIn):
    id: int
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

# Channels
class ChannelIn(BaseModel):
    title: str
    mode: Literal["debate", "critica"] = "debate"
    incognito: bool = False

class ChannelOut(ChannelIn):
    id: int
    created_at: datetime

class ChannelPatch(BaseModel):
    title: str | None = None
    mode: Literal["debate", "critica"] | None = None
    incognito: bool | None = None

# Roster
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

---

## 3. Coste en vivo — TURN_COMPLETE

El orquestador (`orchestrator.py`) ya guarda `cost_usd` por mensaje. Al emitir `TURN_COMPLETE` añade el coste total acumulado del canal:

```json
{"type": "TURN_COMPLETE", "total_cost_usd": "0.00612"}
```

Implementación: `SELECT SUM(cost_usd) FROM messages WHERE channel_id = %s` — nueva query `get_total_cost_usd(channel_id)` en `db/queries/messages.py`. El resultado puede ser `None` si no hay mensajes con coste; en ese caso enviar `"0"`.

El evento TURN_COMPLETE pasa de ser el string literal `"data: [TURN_COMPLETE]\n\n"` a ser un JSON event como los demás:

```
data: {"type": "TURN_COMPLETE", "total_cost_usd": "0.00612"}\n\n
```

**Impacto en clientes:** cualquier cliente que detecte `[TURN_COMPLETE]` en el body necesitará actualizar su parser. En Fase 2A no hay frontend, así que solo afecta a los tests existentes de `test_orchestrator.py` y `test_stream.py`.

---

## 4. LogCentral

Módulo `backend/logger.py` — JSON sink de loguru que escribe a `logs/tertulia.log`:

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

**Puntos de log en la app:**

| Nivel | Dónde | Mensaje |
|-------|-------|---------|
| INFO | `main.py` lifespan startup | `"startup: DB pool initialized"` |
| INFO | `orchestrator.py` inicio de turn | `"turn started channel_id={} profiles={}"` |
| INFO | `orchestrator.py` después de cada perfil | `"turn done profile={} tokens_in={} tokens_out={} cost={}"` |
| ERROR | `orchestrator.py` excepción en stream | `"stream error channel_id={} profile={}: {exc}"` |
| WARNING | `api/stream.py` canal no encontrado | `"channel not found id={}"` |

`loguru` se añade a `requirements.txt`. No hay dependencia de paquete `logcentral` — Vector recoge los ficheros JSON directamente.

---

## 5. Estructura de ficheros nuevos/modificados

```
backend/
├── logger.py                         NUEVO
├── main.py                           MODIFY — importar logger en lifespan
├── requirements.txt                  MODIFY — añadir loguru>=0.7.0
├── schemas/
│   └── models.py                     MODIFY — añadir ProfileIn/Out/Patch, ChannelIn/Out/Patch, RosterAddIn/Patch/Entry
├── db/
│   └── queries/
│       ├── profiles.py               NUEVO — get_profile, list_profiles, insert_profile, update_profile, archive_profile
│       ├── channels.py               MODIFY — añadir list_channels, insert_channel, update_channel, get_roster_entry
│       └── messages.py               MODIFY — añadir get_total_cost_usd
├── api/
│   ├── profiles.py                   NUEVO — router /profiles
│   └── channels.py                   NUEVO — router /channels (CRUD + roster)
├── services/
│   └── orchestrator.py              MODIFY — TURN_COMPLETE con total_cost_usd, logs
└── tests/
    ├── test_profiles_api.py          NUEVO
    ├── test_channels_api.py          NUEVO
    └── test_orchestrator.py         MODIFY — verificar TURN_COMPLETE con total_cost_usd
```

---

## 6. Testing

- **TDD** en todos los ficheros nuevos: test falla → implementación → test pasa.
- **`test_profiles_api.py`** — mocks en queries, cubre: create, list, get, get-404, patch, delete (soft).
- **`test_channels_api.py`** — cubre: create, list, get, patch para canales; add/list/remove/reorder para roster. Incluye test de guardarraíl: añadir 4º tertuliano → 400.
- **`test_orchestrator.py`** — actualizar test existente: TURN_COMPLETE es ahora JSON con `total_cost_usd`; añadir mock de `get_total_cost_usd`.
- **`test_stream.py`** — actualizar el assert de TURN_COMPLETE.
- **LogCentral** — no se testea el sink (I/O de disco); se verifica que `from backend.logger import logger` no lanza.

**Criterio de aceptación:**
```bash
.venv/bin/python -m pytest -v   # todos los tests pasan
curl -N -X POST http://localhost:8765/channels/1/messages ...  # TURN_COMPLETE incluye total_cost_usd
logcentral query --source tertulia --level info   # aparecen logs del turno
```

---

## 7. Guardarraíles MVP

- Máximo 3 tertulianos activos por canal — validar en `POST /channels/{id}/profiles` → 400 si ya hay 3 activos.
- No hay `DELETE` físico de perfiles ni mensajes — siempre soft-delete.
- `PATCH /profiles/{id}` sobrescribe en vivo el `system_prompt` — no hay versionado (guardarraíl del diseño original).
- `tipo` y `created_at` de un perfil no son editables vía PATCH.
