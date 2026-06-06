# Agora

A self-hosted multi-agent chat where the participants are Claude AI instances with distinct personalities, roles, and voices. Bring a topic, pick your *tertulianos*, and let the debate unfold.

![Stack](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![Stack](https://img.shields.io/badge/React-61DAFB?style=flat&logo=react&logoColor=black)
![Stack](https://img.shields.io/badge/Claude-API-orange?style=flat)

---

## What it does

You create a **channel**, choose 1–3 AI personas from your roster (*tertulianos*), write a message, and each one responds in order — each seeing the previous replies in the same turn. The result is a genuine multi-voice debate, not a single model pretending to disagree with itself.

**Two modes:**
- **Debate** — open intellectual discussion with a shared scaffolding prompt
- **Crítica** — structured critique (great for reviewing writing, ideas, or plans)

**Synthesis button** — at any point, hit *Síntesis* and Orson (the Moderator persona) reads the full transcript from the database and produces a structured markdown summary: topic, positions, friction points, the emergent *gestalt*, and open questions. Ready to paste into Obsidian with full Dataview frontmatter.

---

## Stack

| Layer | Choice |
|---|---|
| Backend | FastAPI + Python 3.11 (async), `anthropic` SDK, `aiomysql` |
| Frontend | React 18 + Vite + custom CSS (no Tailwind utility classes) |
| Database | MariaDB — one DB, five tables |
| Streaming | SSE (server-sent events) for token-by-token rendering |
| Auth | None — Tailscale is the perimeter |
| Deploy | nginx → uvicorn, managed with systemd |

No Docker. No vector DB. No auth layer. Runs happily on a single VPS behind Tailscale.

---

## Personas (seed profiles)

The repo ships with nine seed profiles you can import:

| Name | Role | Voice |
|---|---|---|
| Sócrates | Strips assumptions, forces thinking | Terracotta |
| Platón | Argues through myth and allegory | — |
| Tío Gilito | Cost/ROI filter | — |
| Pragmático | Anti-over-engineering, shippable version | — |
| Clodopus | 10x visionary, opens the solution space | — |
| Orson | Moderator — structures and synthesises | — |
| Arkham | Cosmic horror lens (fiction) | — |
| Brandon | Editor — serves the reader, kills darlings (fiction) | — |
| Pratchett | Surgical humour and humanity (fiction) | — |

Each profile has a `system_prompt`, model selection, and a color voice. You can create, edit, and duplicate profiles from the UI.

---

## Features

- **Streaming** — tokens render in real-time as each persona writes
- **Markdown rendering** — both AI and human messages rendered as GFM
- **@mentions** — force a specific persona to respond
- **Another round** — replay the last turn without a new message
- **Autoscroll toggle** — pause scrolling to read mid-stream, resume with one click
- **Export** — full conversation as markdown (copy or download)
- **Synthesis** — structured summary via the Moderator, with Obsidian-ready frontmatter
- **Dark mode**
- **Mobile responsive** — sidebar ↔ chat toggle on small screens
- **Cost display** — accumulated API cost per channel (€)

---

## Project structure

```
agora/
├── backend/
│   ├── api/           # FastAPI routers (channels, profiles, stream, synthesize)
│   ├── db/            # aiomysql connection pool + query modules
│   ├── services/      # orchestrator, LLM calls, context builder, compressor, synthesizer
│   └── main.py
├── frontend/
│   ├── src/
│   │   ├── components/  # chat/, ui/, export/
│   │   ├── screens/     # ChatScreen, CreateScreen, EditorScreen
│   │   ├── services/    # api.js, sse.js
│   │   ├── store/       # Zustand stores (channel, thread, app)
│   │   └── styles/      # tertulia.css, tertulia-screens.css
│   └── nginx.conf       # production nginx config (port 5151)
├── agora-backend.service   # systemd unit
├── agora-frontend.service  # systemd unit (Vite dev server)
├── Makefile
└── docs-disenio/          # design decisions, seed profiles, wireframes
```

---

## Setup

### Requirements

- Python 3.11 + a virtual environment
- Node 18+
- MariaDB with a `tertulia_db` database
- An Anthropic API key

### Install

```bash
git clone https://github.com/Zell0ss/agora
cd agora
make install
```

Create `.env` in the project root:

```env
ANTHROPIC_API_KEY=sk-ant-...
DB_HOST=localhost
DB_PORT=3306
DB_USER=youruser
DB_PASSWORD=yourpassword
DB_NAME=tertulia_db
```

### Development

```bash
make dev      # starts backend (8001) + Vite dev server (5173)
make stop     # kills both
make restart  # stop + dev
make status   # check what's running
make logs     # tail backend stdout
```

### Production (systemd + nginx)

```bash
make deploy           # builds frontend, installs nginx config at port 5151
make install-services # installs and enables systemd units (requires sudo)
```

After `install-services`, both services start on boot:

```bash
systemctl status agora-backend agora-frontend
journalctl -u agora-backend -u agora-frontend -f
```

---

## Architecture notes

**Turn orchestration** — sequential round-robin: human writes → personas respond in order, each seeing the previous replies in the same turn. An `@mention` forces a specific speaker. "Another round" replays without a new human message.

**Context building** — latest rolling summary (if any) + all messages after it, labelled by speaker (`Josem:`, `Sócrates:`, …). Without speaker labels the agents can't distinguish who said what.

**Context compression** — before each turn, if the token window exceeds a threshold, Haiku compresses the oldest chunk into a new summary row. The synthesis endpoint skips this and reads the full transcript directly from the DB.

**Synthesis vs. rolling summary** — deliberately separate. The rolling summary is lossy (for compression). The synthesis reads all `messages` rows and is meant for export.

**No temperature for Claude 4.x** — `claude-sonnet-4-6` and `claude-opus-4-8` reject the `temperature` parameter. It's only sent for older models (e.g. `claude-haiku-4-5-20251001`).

---

## License

MIT
