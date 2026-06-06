# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Producto

Agora (codename interno: tertulia) — chat web en seb01 (Tailscale) donde los "tertulianos" son instancias de Claude vía API con rol/personalidad propios. El usuario crea canales, elige 1–3 tertulianos y debate ideas o textos; todos participan sobre un contexto compartido, reaccionando entre ellos.

**Dos superficies:** Chat (sidebar + conversación con streaming + export MD) y Editor de perfiles.

## Stack (decisiones cerradas)

| Capa | Decisión |
|---|---|
| Backend | FastAPI + Python 3.11 (async), SDK `anthropic`, `aiomysql` |
| Frontend | React 18 + Vite + Tailwind (SPA) |
| DB | MariaDB en seb01, base: `tertulia_db` |
| Streaming | SSE server→cliente (token stream) |
| Deploy | nginx → uvicorn + `systemd`, **Tailscale-only** |
| Auth | Ninguna (Tailscale como barrera); no añadir auth en MVP |
| Logging | LogCentral, source `tertulia` (loguru) |

**NO Docker para esta app** — uvicorn nativo (patrón saxhero). El problema de `host.docker.internal` no aplica.

## Base de datos

Esquema completo en `docs-disenio/agora-disenio-decisiones.md` §5. Tablas:

- `profiles` — tertulianos y facilitadores (soft-delete via `archived`)
- `channels` — conversaciones (`mode`: debate/critica, flag `incognito`)
- `channel_profiles` — roster por canal (`speaking_order`, `active`)
- `messages` — todos los mensajes (`role`: human/persona/system; `tokens_in/out`, `cost_usd`)
- `summaries` — resúmenes rodantes de compresión de contexto

Borrado de perfiles: `archived = TRUE`, nunca `DELETE` físico (ON DELETE RESTRICT en channel_profiles).

## Arquitectura de turnos

**Round-robin secuencial:** humano escribe → tertulianos responden en orden, cada uno ve las respuestas de los anteriores del mismo turno. @mención fuerza quién habla; botón "otra ronda" repite sin nuevo mensaje humano.

**Contexto de canal:** último `summaries.content` + todos los mensajes posteriores ordenados por `created_at`. Transcript etiquetado por hablante (`Josem:`, `Sócrates:`…) — sin esto los agentes no distinguen quién dijo qué.

**Compresión:** antes de construir contexto, si tokens de ventana superan umbral → Haiku comprime el trozo más antiguo → nueva fila en `summaries` → avanza `covers_up_to_msg_id`.

## Constructor de andamio (pieza central)

Función pura: `build_context(perfil, canal, contexto)` → lista de mensajes para la llamada API.

El system prompt sigue esta matriz:

| tipo de perfil ↓ / modo de canal → | `debate` | `critica` |
|---|---|---|
| `tertuliano` | andamio_debate + `system_prompt` | andamio_critica + `system_prompt` |
| `facilitador` | `system_prompt` a secas | `system_prompt` a secas |

El andamio común vive en `docs-disenio/agora-perfiles-semilla.md`. Los facilitadores **nunca** reciben andamio.

**Dos familias de llamadas LLM — mantener separadas en código:**
- **Participantes:** tertulianos/facilitadores (con su voz y personalidad).
- **Utilidad:** casting director, compresor de contexto, Moderador. Son Haiku/Sonnet "de fontanería", sin personalidad.

## Guardarraíles — NO hacer en MVP

- ❌ Docker para esta app
- ❌ Vector DB / Qdrant — todo en MariaDB; casting = LLM, no embeddings
- ❌ Versionado de prompts (`profile_versions`) — solo edición en vivo (sobrescribe)
- ❌ Director-LLM de turnos — round-robin simple + @mención + "otra ronda"
- ❌ Auth compleja / exposición pública directa — Cloudflare Tunnel si algún día, nunca puerto directo
- ❌ Andamio para facilitadores — RUIZ recibe su prompt a secas

## Antes de codear — verificar siempre

1. **Puerto libre en seb01:** consultar `stack.md` → mapa de puertos antes de fijar el de esta app
2. **Model strings:** verificar strings vigentes al código (pueden cambiar). A fecha del doc: `claude-haiku-4-5-20251001`, `claude-sonnet-4-6`, `claude-opus-4-8`
3. **`ANTHROPIC_API_KEY`:** confirmar que está en el env de la sesión/servicio antes de codear

## Quirks conocidos de la API de Anthropic

- **`temperature` deprecated en Claude 4.x** — `claude-sonnet-4-6` y `claude-opus-4-8` rechazan el parámetro `temperature` con error 400. Solo pasarlo en modelos más antiguos (p.ej. `claude-haiku-4-5-20251001`). Ver `_MODELS_NO_TEMPERATURE` en `backend/services/llm.py`.

## Referencia de diseño

- **Decisiones y esquema DB:** `docs-disenio/agora-disenio-decisiones.md`
- **Perfiles semilla y andamio común:** `docs-disenio/agora-perfiles-semilla.md`
- **Prototipo frontend:** `docs-disenio/design_frontend_handoff_agora/Tertulia.html` (abrir en browser; Babel standalone, no es código de producción)

Patrones a reutilizar de otros proyectos: **saxhero** (FastAPI+React+Vite+Tailwind+nginx+systemd), **PiesPlanos** (`anthropic` async + `aiomysql` + MariaDB).
