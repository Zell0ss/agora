# Agora — Plan de implementación

**Fecha:** 2026-06-06
**Estado:** aprobado — listo para plan de implementación
**Sesión:** brainstorming Josem × Claude Code

---

## Contexto

Agora (codename: tertulia) es un chat web donde los "tertulianos" son instancias de Claude que debaten ideas en grupo. El diseño del producto está completamente asentado en `docs-disenio/agora-disenio-decisiones.md`. Este doc cubre únicamente las decisiones de implementación tomadas en esta sesión.

---

## Decisiones de implementación

### Stack (reafirmado del diseño)

| Capa | Decisión |
|---|---|
| Backend | FastAPI + Python 3.11 async, SDK `anthropic`, `aiomysql` |
| Frontend | React 18 + Vite + Tailwind (SPA) — Fase 3 |
| DB | MariaDB en seb01, base: `tertulia_db`, SQL manual |
| Streaming | SSE server→cliente |
| Deploy | nginx → uvicorn + systemd, Tailscale-only |
| Migrations | Script SQL manual (`init.sql`). Sin Alembic en MVP. |

### Estructura de directorios

```
agora/
├── backend/
│   ├── main.py               # FastAPI app + lifespan (pool DB)
│   ├── config.py             # Settings desde .env (Pydantic BaseSettings)
│   ├── requirements.txt
│   ├── db/
│   │   ├── connection.py     # Pool aiomysql, get_db() context manager
│   │   ├── init.sql          # Schema completo (de agora-disenio-decisiones.md §5)
│   │   └── queries/
│   │       ├── profiles.py   # get_profile, list_profiles, insert_profile, archive_profile
│   │       ├── channels.py   # get_channel, list_channels, insert_channel, get_active_roster
│   │       └── messages.py   # insert_message, get_context_messages, get_latest_summary
│   ├── services/
│   │   ├── andamio.py        # build_context(perfil, canal, historial) → list[dict] para API
│   │   ├── llm.py            # stream_turn(messages, model, temp) → AsyncGenerator[str]
│   │   ├── orchestrator.py   # run_turn(canal_id, human_msg) → AsyncGenerator[ServerSentEvent]
│   │   ├── profiles.py       # Lógica de negocio de perfiles
│   │   └── channels.py       # Lógica de negocio de canales
│   ├── api/
│   │   ├── profiles.py       # Router /profiles
│   │   ├── channels.py       # Router /channels
│   │   └── stream.py         # Router /channels/{id}/messages → SSE
│   └── schemas/
│       └── models.py         # Pydantic: Profile, Channel, Message, TurnRequest, SSEEvent
└── frontend/                 # Fase 3 — React + Vite + Tailwind
```

### Enfoque de construcción: slice vertical fino primero

En lugar de construir todas las capas de un dominio antes de pasar al siguiente, se construye el camino feliz completo (un canal → un tertuliano → un turno → streaming SSE) antes de expandir horizontalmente. Esto valida la integración de todas las capas y el contrato SSE en días, no semanas.

---

## Fase 1 — Slice vertical (objetivo: `curl` → tokens en pantalla)

### Alcance exacto de Fase 1

**Incluido:**
- Schema DB en MariaDB (`tertulia_db`) + seed con INSERTs en `init.sql`: 1 perfil (Sócrates) y 1 canal
- Pool aiomysql + config desde `.env`
- `db/queries/` — solo las queries del slice: `get_active_roster`, `insert_message`, `get_context_messages`. El resto (CRUD completo de perfiles/canales) se completa en Fase 2.
- `andamio.py` — función pura `build_context()` (sin lógica de compresión aún)
- `llm.py` — `stream_turn()` con `anthropic.messages.stream()` async
- `orchestrator.py` — un tertuliano, un turno (sin round-robin multi-agente aún)
- `api/stream.py` — `POST /channels/{id}/messages` que devuelve `StreamingResponse` SSE
- `main.py` — app FastAPI mínima con lifespan para el pool DB
- `schemas/models.py` — modelos mínimos para el endpoint de streaming

**Excluido de Fase 1:**
- CRUD de perfiles y canales (rutas GET/POST/PATCH)
- Multi-tertuliano round-robin
- Compresión de contexto (rolling summary)
- @mención, "otra ronda", casting director
- Coste en vivo / LogCentral
- Export Markdown
- Frontend

### Criterio de éxito de Fase 1

```bash
curl -N -X POST http://localhost:{PORT}/channels/1/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "¿Debería lanzar esto como SaaS?"}'
```

Respuesta esperada: stream SSE con los tokens de Sócrates llegando en tiempo real, mensaje guardado en DB con `tokens_in`, `tokens_out`, `cost_usd`.

---

## Fase 2 — Expansión horizontal

En orden de prioridad:

1. CRUD completo: profiles, channels, channel_profiles
2. Multi-tertuliano round-robin (hasta 3, cada uno ve las respuestas anteriores del turno)
3. Compresión de contexto — Haiku comprime ventana antigua → `summaries`
4. @mención (fuerza `speaking_order` del turno)
5. Botón "otra ronda" (repite turno sin nuevo mensaje humano)
6. Coste en vivo — `SUM(cost_usd)` por canal en cada respuesta
7. LogCentral — source `tertulia`, loguru
8. Casting director — Haiku sugiere 2-3 tertulianos por diversidad de ángulo
9. Export Markdown — llamada de utilidad al Moderador sobre contexto del canal

---

## Fase 3 — Frontend + Deploy

1. Scaffold React 18 + Vite + Tailwind en `frontend/`
2. SSE client (EventSource API) + UI de streaming (caret animado)
3. Chat 3 columnas + sidebar + editor de perfiles (según handoff en `docs-disenio/`)
4. nginx → uvicorn + systemd service
5. Puerto libre — verificar `stack.md` antes de fijar
6. Tailscale-only, sin exposición pública directa

---

## Cuestiones abiertas (heredadas del diseño)

- Puerto exacto en seb01 (verificar `stack.md`)
- Umbral de tokens para compresión — afinar empíricamente en Fase 2
- "Otra ronda": una vuelta en MVP, selector N-rondas con tope duro en futuro
- RUIZ: ¿Spanish-ificar el prompt o mantener en inglés?
