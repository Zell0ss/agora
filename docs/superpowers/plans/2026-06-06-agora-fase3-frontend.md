# Agora Frontend React — Implementation Plan (Fase 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete React 18 + Vite frontend for Agora, wiring it to the existing FastAPI backend with SSE streaming, @mention autocomplete, profile editor, and mobile layout at 412px.

**Architecture:** Three screens (Chat, Create, Editor) with React Router DOM v6; Zustand for streaming state; CSS variables from design handoff ported verbatim to `src/styles/`; `fetch()` + `ReadableStream` for SSE since the backend uses POST endpoints.

**Tech Stack:** React 18, Vite, Tailwind v3, Zustand, React Router DOM v6, Vitest; backend FastAPI on :8001; dev proxy `/api → localhost:8001`.

---

## Field name mapping (backend → frontend)

The backend schema uses different names than the design prototype. Always use the backend names when calling the API:

| Backend field | Frontend display | Notes |
|---|---|---|
| `profile.color` | `voice` (`data-voice` attr) | Values: `"vera"`, `"bruno"`, `"iris"` |
| `profile.funcion` | role label | Shown in chips |
| `profile.tipo` | type | `"tertuliano"` or `"facilitador"` |
| `profile.temperature` | `temp` | 0–1 float |
| `profile.model` | display name | Map: `"claude-sonnet-4-6"` → `"Claude Sonnet"`, `"claude-opus-4-8"` → `"Claude Opus"`, `"claude-haiku-4-5-20251001"` → `"Claude Haiku"` |

---

## Task 1: Backend — GET /channels/{id}/messages

**Files:**
- Modify: `backend/db/queries/messages.py`
- Modify: `backend/schemas/models.py`
- Modify: `backend/api/channels.py`
- Modify: `backend/tests/test_channels.py` (create if missing)

The frontend needs to load conversation history when switching channels. This endpoint doesn't exist yet.

- [ ] **Step 1: Write the failing test**

Create or open `backend/tests/test_channels.py` and add:

```python
from unittest.mock import AsyncMock, patch
import pytest


@pytest.mark.asyncio
async def test_list_channel_messages_returns_history():
    from backend.api.channels import router  # noqa: F401 — ensures route registered
    from fastapi.testclient import TestClient
    from backend.main import app

    mock_msgs = [
        {"id": 1, "role": "human", "profile_id": None,
         "content": "Hola", "cost_usd": None, "created_at": "2026-01-01T10:00:00"},
        {"id": 2, "role": "persona", "profile_id": 1,
         "content": "Buenos días", "cost_usd": 0.0001, "created_at": "2026-01-01T10:00:05"},
    ]
    with (
        patch("backend.api.channels.get_channel", AsyncMock(return_value={"id": 1})),
        patch("backend.api.channels.get_channel_messages", AsyncMock(return_value=mock_msgs)),
    ):
        client = TestClient(app)
        resp = client.get("/channels/1/messages")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["role"] == "human"
    assert data[1]["profile_id"] == 1


@pytest.mark.asyncio
async def test_list_channel_messages_404_unknown_channel():
    from fastapi.testclient import TestClient
    from backend.main import app

    with patch("backend.api.channels.get_channel", AsyncMock(return_value=None)):
        client = TestClient(app)
        resp = client.get("/channels/99/messages")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /data/agora && source .venv/bin/activate
pytest backend/tests/test_channels.py -v 2>&1 | tail -20
```

Expected: FAIL — `get_channel_messages` not found / 404 on valid channel.

- [ ] **Step 3: Add query to messages.py**

Append to `backend/db/queries/messages.py`:

```python
async def get_channel_messages(channel_id: int) -> list[dict]:
    async with get_db() as cur:
        await cur.execute(
            """
            SELECT id, role, profile_id, content, cost_usd, created_at
            FROM messages
            WHERE channel_id = %s
            ORDER BY created_at ASC
            """,
            (channel_id,),
        )
        return await cur.fetchall()
```

- [ ] **Step 4: Add schema to models.py**

In `backend/schemas/models.py`, add after the `ChannelPatch` class:

```python
class MessageOut(BaseModel):
    id: int
    role: str
    profile_id: int | None
    content: str
    cost_usd: float | None
    created_at: datetime
```

- [ ] **Step 5: Add endpoint to channels.py**

At the top of `backend/api/channels.py`, add to imports:

```python
from backend.db.queries.messages import get_channel_messages
from backend.schemas.models import MessageOut
```

Then add this endpoint after the `patch_channel` handler:

```python
@router.get("/{channel_id}/messages", response_model=list[MessageOut])
async def list_channel_messages(channel_id: int):
    channel = await get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")
    return await get_channel_messages(channel_id)
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest backend/tests/test_channels.py -v 2>&1 | tail -20
```

Expected: PASS all.

- [ ] **Step 7: Commit**

```bash
git add backend/db/queries/messages.py backend/schemas/models.py \
        backend/api/channels.py backend/tests/test_channels.py
git commit -m "feat: add GET /channels/{id}/messages endpoint for frontend history"
```

---

## Task 2: Frontend scaffold

**Files:**
- Create: `frontend/` (whole directory via Vite)
- Create: `frontend/vite.config.js`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/postcss.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/index.css`
- Create: `frontend/src/styles/tertulia.css`
- Create: `frontend/src/styles/tertulia-screens.css`
- Create: `frontend/src/styles/tertulia-mobile.css`

- [ ] **Step 1: Scaffold Vite + React**

```bash
cd /data/agora
npm create vite@latest frontend -- --template react
cd frontend
npm install
```

- [ ] **Step 2: Install deps**

```bash
cd /data/agora/frontend
npm install zustand react-router-dom
npm install -D tailwindcss@3 postcss autoprefixer vitest @testing-library/react @testing-library/user-event jsdom @vitejs/plugin-react
npx tailwindcss init -p
```

- [ ] **Step 3: Write vite.config.js**

Replace the generated `frontend/vite.config.js` with:

```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test-setup.js',
  },
})
```

- [ ] **Step 4: Write tailwind.config.js**

Replace the generated `frontend/tailwind.config.js` with:

```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: { extend: {} },
  plugins: [],
}
```

- [ ] **Step 5: Write src/index.css (Tailwind only)**

Replace the generated `frontend/src/index.css` with:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 6: Port the design CSS files**

Copy the three CSS files from the design handoff verbatim:

```bash
cp /data/agora/docs-disenio/design_frontend_handoff_agora/tertulia.css \
   /data/agora/frontend/src/styles/tertulia.css
cp /data/agora/docs-disenio/design_frontend_handoff_agora/tertulia-screens.css \
   /data/agora/frontend/src/styles/tertulia-screens.css
cp /data/agora/docs-disenio/design_frontend_handoff_agora/tertulia-mobile.css \
   /data/agora/frontend/src/styles/tertulia-mobile.css
```

- [ ] **Step 7: Update index.html**

Replace `frontend/index.html` with:

```html
<!doctype html>
<html lang="es">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Agora</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,400&family=Hanken+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

- [ ] **Step 8: Create test setup file**

Create `frontend/src/test-setup.js`:

```js
import '@testing-library/jest-dom'
```

Install the missing dep:

```bash
cd /data/agora/frontend && npm install -D @testing-library/jest-dom
```

- [ ] **Step 9: Verify Vite starts**

```bash
cd /data/agora/frontend && npm run dev &
sleep 3 && curl -s http://localhost:5173 | grep -c "root"
```

Expected: `1` (the `#root` div is present).

Kill the dev server: `kill %1`

- [ ] **Step 10: Commit**

```bash
cd /data/agora
git add frontend/
git commit -m "feat: scaffold React 18 + Vite + Tailwind + Zustand frontend"
```

---

## Task 3: Zustand stores

**Files:**
- Create: `frontend/src/store/useAppStore.js`
- Create: `frontend/src/store/useChannelStore.js`
- Create: `frontend/src/store/useThreadStore.js`
- Create: `frontend/src/store/useAppStore.test.js`
- Create: `frontend/src/store/useThreadStore.test.js`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/store/useAppStore.test.js`:

```js
import { describe, it, expect, beforeEach } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { useAppStore } from './useAppStore'

describe('useAppStore', () => {
  beforeEach(() => useAppStore.setState({ theme: 'light' }))

  it('starts with light theme', () => {
    const { result } = renderHook(() => useAppStore())
    expect(result.current.theme).toBe('light')
  })

  it('toggleTheme switches to dark', () => {
    const { result } = renderHook(() => useAppStore())
    act(() => result.current.toggleTheme())
    expect(result.current.theme).toBe('dark')
  })

  it('toggleTheme switches back to light', () => {
    useAppStore.setState({ theme: 'dark' })
    const { result } = renderHook(() => useAppStore())
    act(() => result.current.toggleTheme())
    expect(result.current.theme).toBe('light')
  })
})
```

Create `frontend/src/store/useThreadStore.test.js`:

```js
import { describe, it, expect, beforeEach } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { useThreadStore } from './useThreadStore'

const INITIAL = { messages: [], thinking: new Set(), accumulatedCost: '0', error: null }

describe('useThreadStore', () => {
  beforeEach(() => useThreadStore.setState(INITIAL))

  it('addUserMessage appends a human message', () => {
    const { result } = renderHook(() => useThreadStore())
    act(() => result.current.addUserMessage('Hola'))
    expect(result.current.messages).toHaveLength(1)
    expect(result.current.messages[0].role).toBe('human')
    expect(result.current.messages[0].content).toBe('Hola')
  })

  it('addThinking adds profileId to thinking set', () => {
    const { result } = renderHook(() => useThreadStore())
    act(() => result.current.addThinking(42))
    expect(result.current.thinking.has(42)).toBe(true)
  })

  it('appendToken creates streaming message on first call', () => {
    const { result } = renderHook(() => useThreadStore())
    act(() => result.current.appendToken(1, 'Hola'))
    expect(result.current.messages).toHaveLength(1)
    expect(result.current.messages[0].streaming).toBe(true)
    expect(result.current.messages[0].content).toBe('Hola')
  })

  it('appendToken accumulates tokens on subsequent calls', () => {
    const { result } = renderHook(() => useThreadStore())
    act(() => result.current.appendToken(1, 'Hola'))
    act(() => result.current.appendToken(1, ' mundo'))
    expect(result.current.messages).toHaveLength(1)
    expect(result.current.messages[0].content).toBe('Hola mundo')
  })

  it('finalizeMessage clears streaming flag and removes from thinking', () => {
    const { result } = renderHook(() => useThreadStore())
    act(() => result.current.addThinking(1))
    act(() => result.current.appendToken(1, 'Texto'))
    act(() => result.current.finalizeMessage(1, { costUsd: '0.0001' }))
    expect(result.current.thinking.has(1)).toBe(false)
    expect(result.current.messages[0].streaming).toBe(false)
    expect(result.current.messages[0].costUsd).toBe('0.0001')
  })

  it('setCost updates accumulatedCost and clears error', () => {
    const { result } = renderHook(() => useThreadStore())
    act(() => { result.current.setError('boom'); result.current.setCost('0.05') })
    expect(result.current.accumulatedCost).toBe('0.05')
    expect(result.current.error).toBeNull()
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /data/agora/frontend && npx vitest run src/store/ 2>&1 | tail -20
```

Expected: FAIL — modules not found.

- [ ] **Step 3: Implement useAppStore.js**

Create `frontend/src/store/useAppStore.js`:

```js
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export const useAppStore = create(
  persist(
    (set) => ({
      theme: 'light',
      toggleTheme: () =>
        set((s) => ({ theme: s.theme === 'light' ? 'dark' : 'light' })),
    }),
    { name: 'agora-app' }
  )
)
```

- [ ] **Step 4: Implement useThreadStore.js**

Create `frontend/src/store/useThreadStore.js`:

```js
import { create } from 'zustand'

export const useThreadStore = create((set) => ({
  messages: [],
  thinking: new Set(),
  accumulatedCost: '0',
  error: null,

  setMessages: (messages) => set({ messages }),

  addUserMessage: (content) =>
    set((s) => ({
      messages: [
        ...s.messages,
        {
          id: `user-${Date.now()}`,
          role: 'human',
          profileId: null,
          content,
          time: new Date().toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit' }),
          streaming: false,
          costUsd: null,
        },
      ],
    })),

  addThinking: (profileId) =>
    set((s) => ({ thinking: new Set([...s.thinking, profileId]) })),

  appendToken: (profileId, chunk) =>
    set((s) => {
      const existing = s.messages.find((m) => m.profileId === profileId && m.streaming)
      if (existing) {
        return {
          messages: s.messages.map((m) =>
            m.profileId === profileId && m.streaming
              ? { ...m, content: m.content + chunk }
              : m
          ),
        }
      }
      return {
        messages: [
          ...s.messages,
          {
            id: `stream-${profileId}-${Date.now()}`,
            role: 'persona',
            profileId,
            content: chunk,
            time: null,
            streaming: true,
            costUsd: null,
          },
        ],
      }
    }),

  finalizeMessage: (profileId, meta) =>
    set((s) => ({
      thinking: new Set([...s.thinking].filter((id) => id !== profileId)),
      messages: s.messages.map((m) =>
        m.profileId === profileId && m.streaming
          ? {
              ...m,
              streaming: false,
              time: new Date().toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit' }),
              costUsd: meta.costUsd,
            }
          : m
      ),
    })),

  setCost: (total) => set({ accumulatedCost: total, error: null }),
  setError: (msg) => set({ error: msg }),
  clearError: () => set({ error: null }),
}))
```

- [ ] **Step 5: Implement useChannelStore.js**

Create `frontend/src/store/useChannelStore.js`:

```js
import { create } from 'zustand'
import { getChannels, getRoster, getChannelMessages, getProfiles } from '../services/api'
import { useThreadStore } from './useThreadStore'

export const useChannelStore = create((set) => ({
  channels: [],
  activeChannelId: null,
  roster: [],   // enriched: RosterEntry merged with ProfileOut (adds color, funcion)

  fetchChannels: async () => {
    const channels = await getChannels()
    set({ channels })
  },

  setActive: async (channelId) => {
    set({ activeChannelId: channelId, roster: [] })
    useThreadStore.getState().setMessages([])

    // Fetch roster entries, all profiles, and message history in parallel.
    // RosterEntry only has {profile_id, name, tipo, speaking_order, active}.
    // ProfileOut adds {color, funcion, model, temperature, system_prompt}.
    // We merge them so components can access voice color and role label.
    const [rosterEntries, allProfiles, rawMessages] = await Promise.all([
      getRoster(channelId),
      getProfiles(),
      getChannelMessages(channelId),
    ])

    const profileMap = Object.fromEntries(allProfiles.map((p) => [p.id, p]))
    const roster = rosterEntries.map((entry) => ({
      ...profileMap[entry.profile_id],  // color, funcion, model, temperature, system_prompt
      ...entry,                         // profile_id, name, tipo, speaking_order, active
    }))

    const messages = rawMessages.map((m) => ({
      id: m.id,
      role: m.role,
      profileId: m.profile_id,
      content: m.content,
      time: new Date(m.created_at).toLocaleTimeString('es', {
        hour: '2-digit',
        minute: '2-digit',
      }),
      streaming: false,
      costUsd: m.cost_usd ? String(m.cost_usd) : null,
    }))

    set({ roster })
    useThreadStore.getState().setMessages(messages)
  },

  addChannel: (channel) =>
    set((s) => ({ channels: [channel, ...s.channels] })),
}))
```

- [ ] **Step 6: Run tests**

```bash
cd /data/agora/frontend && npx vitest run src/store/ 2>&1 | tail -20
```

Expected: PASS all (useChannelStore has no unit tests; it will be covered by integration).

- [ ] **Step 7: Commit**

```bash
cd /data/agora
git add frontend/src/store/
git commit -m "feat: add Zustand stores (app theme, channel, thread streaming)"
```

---

## Task 4: API + SSE services

**Files:**
- Create: `frontend/src/services/api.js`
- Create: `frontend/src/services/sse.js`
- Create: `frontend/src/services/sse.test.js`

- [ ] **Step 1: Write SSE parser tests**

Create `frontend/src/services/sse.test.js`:

```js
import { describe, it, expect } from 'vitest'
import { parseSSEChunk } from './sse'

describe('parseSSEChunk', () => {
  it('parses a complete data line', () => {
    const events = []
    const leftover = parseSSEChunk(
      'data: {"type":"token","profile_id":1,"token":"Hola"}\n\n',
      '',
      (e) => events.push(e)
    )
    expect(events).toHaveLength(1)
    expect(events[0].type).toBe('token')
    expect(events[0].token).toBe('Hola')
    expect(leftover).toBe('')
  })

  it('handles chunks split across boundaries', () => {
    const events = []
    const partial = parseSSEChunk('data: {"type":"star', '', (e) => events.push(e))
    expect(events).toHaveLength(0)
    const leftover = parseSSEChunk('t","profile_id":1}\n\n', partial, (e) => events.push(e))
    expect(events).toHaveLength(1)
    expect(events[0].type).toBe('start')
    expect(leftover).toBe('')
  })

  it('parses multiple events in one chunk', () => {
    const events = []
    parseSSEChunk(
      'data: {"type":"start","profile_id":1}\n\ndata: {"type":"token","profile_id":1,"token":"A"}\n\n',
      '',
      (e) => events.push(e)
    )
    expect(events).toHaveLength(2)
    expect(events[0].type).toBe('start')
    expect(events[1].type).toBe('token')
  })

  it('ignores empty data lines', () => {
    const events = []
    parseSSEChunk('data: \n\n', '', (e) => events.push(e))
    expect(events).toHaveLength(0)
  })
})
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd /data/agora/frontend && npx vitest run src/services/sse.test.js 2>&1 | tail -10
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement sse.js**

Create `frontend/src/services/sse.js`:

```js
/**
 * parseSSEChunk: pure function for testing. Processes one decoded text chunk,
 * prepending any leftover from previous chunk. Returns new leftover.
 */
export function parseSSEChunk(text, leftover, onEvent) {
  const combined = leftover + text
  const parts = combined.split('\n\n')
  const remaining = parts.pop() // may be incomplete

  for (const part of parts) {
    for (const line of part.split('\n')) {
      if (!line.startsWith('data: ')) continue
      const json = line.slice(6).trim()
      if (!json) continue
      try {
        onEvent(JSON.parse(json))
      } catch {
        // malformed JSON — skip
      }
    }
  }
  return remaining
}

async function consumeStream(body, onEvent) {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let leftover = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    leftover = parseSSEChunk(decoder.decode(value, { stream: true }), leftover, onEvent)
  }
}

export async function streamTurn(channelId, content, handlers) {
  const { onStart, onToken, onDone, onComplete, onError } = handlers
  try {
    const resp = await fetch(`/api/channels/${channelId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    await consumeStream(resp.body, (evt) => dispatchEvent(evt, handlers))
  } catch (err) {
    onError(err.message)
  }
}

export async function streamRound(channelId, handlers) {
  const { onError } = handlers
  try {
    const resp = await fetch(`/api/channels/${channelId}/rounds`, { method: 'POST' })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    await consumeStream(resp.body, (evt) => dispatchEvent(evt, handlers))
  } catch (err) {
    onError(err.message)
  }
}

function dispatchEvent(evt, { onStart, onToken, onDone, onComplete }) {
  switch (evt.type) {
    case 'start':
      onStart(evt.profile_id, evt.profile_name)
      break
    case 'token':
      onToken(evt.profile_id, evt.token)
      break
    case 'done':
      onDone(evt.profile_id, {
        tokensIn: evt.tokens_in,
        tokensOut: evt.tokens_out,
        costUsd: evt.cost_usd,
      })
      break
    case 'TURN_COMPLETE':
      onComplete(evt.total_cost_usd)
      break
  }
}
```

- [ ] **Step 4: Implement api.js**

Create `frontend/src/services/api.js`:

```js
const BASE = '/api'

async function request(method, path, body) {
  const opts = { method, headers: {} }
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(body)
  }
  const resp = await fetch(BASE + path, opts)
  if (!resp.ok) {
    const text = await resp.text()
    throw new Error(`${resp.status}: ${text}`)
  }
  if (resp.status === 204) return null
  return resp.json()
}

// Channels
export const getChannels = () => request('GET', '/channels')
export const createChannel = (body) => request('POST', '/channels', body)
export const getChannelMessages = (id) => request('GET', `/channels/${id}/messages`)
export const getRoster = (id) => request('GET', `/channels/${id}/profiles`)
export const addToRoster = (channelId, body) =>
  request('POST', `/channels/${channelId}/profiles`, body)
export const removeFromRoster = (channelId, profileId) =>
  request('DELETE', `/channels/${channelId}/profiles/${profileId}`)

// Profiles
export const getProfiles = () => request('GET', '/profiles')
export const createProfile = (body) => request('POST', '/profiles', body)
export const patchProfile = (id, body) => request('PATCH', `/profiles/${id}`, body)
export const deleteProfile = (id) => request('DELETE', `/profiles/${id}`)
```

- [ ] **Step 5: Run SSE tests**

```bash
cd /data/agora/frontend && npx vitest run src/services/sse.test.js 2>&1 | tail -10
```

Expected: PASS all 4 tests.

- [ ] **Step 6: Commit**

```bash
cd /data/agora
git add frontend/src/services/
git commit -m "feat: add API service and SSE stream parser"
```

---

## Task 5: UI atoms

**Files:**
- Create: `frontend/src/components/ui/Icon.jsx`
- Create: `frontend/src/components/ui/Avatar.jsx`
- Create: `frontend/src/components/ui/AvatarStack.jsx`

These are ported directly from `tertulia-ui.jsx` in the design handoff, adapted to proper React (no `window.TERT` globals).

- [ ] **Step 1: Create Icon.jsx**

Create `frontend/src/components/ui/Icon.jsx`:

```jsx
export const Ico = {
  plus:     'M10 4v12M4 10h12',
  search:   'M9 3a6 6 0 104.2 10.3L17 17M9 3a6 6 0 014.2 10.3',
  send:     'M4 10l13-6-6 13-2.2-4.8L4 10z',
  round:    'M16 5v4h-4M15.5 9A6 6 0 105 13',
  export:   'M10 3v9m0-9L7 6m3-3l3 3M4 13v2.5A1.5 1.5 0 005.5 17h9a1.5 1.5 0 001.5-1.5V13',
  userplus: 'M12.5 16v-1.5A2.5 2.5 0 0010 12H5.5A2.5 2.5 0 003 14.5V16M7.75 9a2.5 2.5 0 100-5 2.5 2.5 0 000 5M16 6v4M18 8h-4',
  chevron:  'M5 8l5 5 5-5',
  copy:     'M7 7V4.5A1.5 1.5 0 018.5 3h7A1.5 1.5 0 0117 4.5v7a1.5 1.5 0 01-1.5 1.5H13M11.5 7h-7A1.5 1.5 0 003 8.5v7A1.5 1.5 0 004.5 17h7a1.5 1.5 0 001.5-1.5v-7A1.5 1.5 0 0011.5 7z',
  download: 'M10 3v9m0 0l3.2-3.2M10 12L6.8 8.8M4 15.5h12',
  check:    'M4 10.5l4 4 8-9',
  warn:     'M10 3.5l7 12H3l7-12zM10 8.5v3.5M10 14.2v.2',
  sun:      ['M10 7.2a2.8 2.8 0 100 5.6 2.8 2.8 0 000-5.6',
             'M10 2.6v1.8M10 15.6v1.8M2.6 10h1.8M15.6 10h1.8M4.8 4.8l1.3 1.3M13.9 13.9l1.3 1.3M15.2 4.8l-1.3 1.3M6.1 13.9l-1.3 1.3'],
  moon:     'M15.4 11.3A6 6 0 117.7 3.6 4.8 4.8 0 0015.4 11.3z',
}

export default function Icon({ d, size = 20, stroke = 1.6, fill = 'none', style }) {
  return (
    <svg
      width={size} height={size} viewBox="0 0 20 20"
      fill={fill}
      stroke={fill === 'none' ? 'currentColor' : 'none'}
      strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round"
      style={{ flex: '0 0 auto', ...style }}
    >
      {(Array.isArray(d) ? d : [d]).map((p, i) => <path key={i} d={p} />)}
    </svg>
  )
}
```

- [ ] **Step 2: Create Avatar.jsx**

Create `frontend/src/components/ui/Avatar.jsx`:

```jsx
export default function Avatar({ profile, size = 34, ring }) {
  const isUser = !profile
  const cls = ['t-av', isUser ? 'is-user' : ''].filter(Boolean).join(' ')
  const style = { '--sz': size + 'px', fontSize: Math.round(size * 0.42) + 'px' }
  if (ring) style['--ring'] = ring

  return (
    <div
      className={cls}
      data-voice={isUser ? undefined : profile.color}
      style={style}
    >
      {isUser ? 'T' : (profile.name?.charAt(0) ?? '?')}
    </div>
  )
}
```

Note: `profile.color` holds the voice identifier (`"vera"`, `"bruno"`, `"iris"`). The `data-voice` attribute activates the CSS voice variables (`--vc`, `--vt`) on the element.

- [ ] **Step 3: Create AvatarStack.jsx**

Create `frontend/src/components/ui/AvatarStack.jsx`:

```jsx
import Avatar from './Avatar'

export default function AvatarStack({ profiles = [], size = 26, ring }) {
  return (
    <div className="t-stack" style={ring ? { '--ring': ring } : undefined}>
      {profiles.map((p) => (
        <Avatar key={p.profile_id ?? p.id} profile={p} size={size} ring={ring} />
      ))}
    </div>
  )
}
```

- [ ] **Step 4: Commit**

```bash
cd /data/agora
git add frontend/src/components/ui/
git commit -m "feat: add Icon, Avatar, AvatarStack UI atoms"
```

---

## Task 6: App shell + routing

**Files:**
- Create: `frontend/src/main.jsx`
- Create: `frontend/src/App.jsx`
- Create: `frontend/src/screens/ChatScreen.jsx` (stub)
- Create: `frontend/src/screens/CreateScreen.jsx` (stub)
- Create: `frontend/src/screens/EditorScreen.jsx` (stub)

- [ ] **Step 1: Write main.jsx**

Replace the generated `frontend/src/main.jsx`:

```jsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './styles/tertulia.css'
import './styles/tertulia-screens.css'
import './styles/tertulia-mobile.css'
import './index.css'
import App from './App'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>
)
```

- [ ] **Step 2: Write App.jsx**

Create `frontend/src/App.jsx`:

```jsx
import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAppStore } from './store/useAppStore'
import { useChannelStore } from './store/useChannelStore'
import ChatScreen from './screens/ChatScreen'
import CreateScreen from './screens/CreateScreen'
import EditorScreen from './screens/EditorScreen'

export default function App() {
  const theme = useAppStore((s) => s.theme)
  const fetchChannels = useChannelStore((s) => s.fetchChannels)

  useEffect(() => {
    document.documentElement.classList.toggle('t-dark', theme === 'dark')
  }, [theme])

  useEffect(() => {
    fetchChannels()
  }, [fetchChannels])

  return (
    <div className={`t${theme === 'dark' ? ' t-dark' : ''}`} style={{ height: '100vh', overflow: 'hidden' }}>
      <Routes>
        <Route path="/" element={<ChatScreen />} />
        <Route path="/channels/new" element={<CreateScreen />} />
        <Route path="/profiles" element={<EditorScreen />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  )
}
```

- [ ] **Step 3: Create screen stubs**

Create `frontend/src/screens/ChatScreen.jsx`:

```jsx
export default function ChatScreen() {
  return <div className="t-app"><p>Chat (coming soon)</p></div>
}
```

Create `frontend/src/screens/CreateScreen.jsx`:

```jsx
export default function CreateScreen() {
  return <div className="t-sheet"><p>Create (coming soon)</p></div>
}
```

Create `frontend/src/screens/EditorScreen.jsx`:

```jsx
export default function EditorScreen() {
  return <div className="t-editor"><p>Editor (coming soon)</p></div>
}
```

- [ ] **Step 4: Verify app renders**

Start the backend first (if not running):

```bash
cd /data/agora && source .venv/bin/activate
uvicorn backend.main:app --host 127.0.0.1 --port 8001 &
```

Then start Vite:

```bash
cd /data/agora/frontend && npm run dev &
sleep 3 && curl -s http://localhost:5173 | grep -c "Agora"
```

Expected: `1` (title tag present). Open browser at `http://localhost:5173` — should show "Chat (coming soon)".

- [ ] **Step 5: Commit**

```bash
cd /data/agora
git add frontend/src/main.jsx frontend/src/App.jsx frontend/src/screens/
git commit -m "feat: add App shell with React Router and theme sync"
```

---

## Task 7: Sidebar + ChatHeader

**Files:**
- Create: `frontend/src/components/chat/Sidebar.jsx`
- Create: `frontend/src/components/chat/ChatHeader.jsx`

- [ ] **Step 1: Create Sidebar.jsx**

Create `frontend/src/components/chat/Sidebar.jsx`:

```jsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Icon, { Ico } from '../ui/Icon'
import AvatarStack from '../ui/AvatarStack'
import { useAppStore } from '../../store/useAppStore'
import { useChannelStore } from '../../store/useChannelStore'

function ThemeToggle() {
  const { theme, toggleTheme } = useAppStore()
  return (
    <button className="t-themesw" onClick={toggleTheme} aria-label="Cambiar tema">
      <span className={`t-themesw-opt${theme === 'light' ? ' is-on' : ''}`}>
        <Icon d={Ico.sun} size={15} />
      </span>
      <span className={`t-themesw-opt${theme === 'dark' ? ' is-on' : ''}`}>
        <Icon d={Ico.moon} size={14} />
      </span>
    </button>
  )
}

export default function Sidebar() {
  const [search, setSearch] = useState('')
  const navigate = useNavigate()
  const { channels, activeChannelId, setActive } = useChannelStore()

  const filtered = channels.filter((c) =>
    c.title.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <aside className="t-side">
      <div className="t-side-top">
        <div className="t-brandrow">
          <div className="t-wordmark">Agora<span className="dot">.</span></div>
          <ThemeToggle />
        </div>
        <button className="t-newbtn" onClick={() => navigate('/channels/new')}>
          <Icon d={Ico.plus} size={18} />Nuevo canal
        </button>
      </div>

      <div className="t-search">
        <Icon d={Ico.search} size={16} />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Buscar canal…"
          style={{ background: 'none', border: 'none', outline: 'none', flex: 1, font: 'inherit', color: 'inherit' }}
        />
      </div>

      <div className="t-side-list t-scroll">
        <div className="t-side-label">Canales</div>
        {filtered.map((c) => (
          <div
            key={c.id}
            className={`t-chan${c.id === activeChannelId ? ' is-active' : ''}`}
            onClick={() => setActive(c.id)}
            style={{ cursor: 'pointer' }}
          >
            <div className="t-chan-av">
              <AvatarStack
                profiles={c.roster ?? []}
                size={26}
                ring={c.id === activeChannelId ? 'var(--surface)' : 'var(--sidebar)'}
              />
            </div>
            <div className="t-chan-mid">
              <div className="t-chan-title">{c.title || 'Sin título'}</div>
              <div className="t-chan-prev">{c.preview ?? ''}</div>
            </div>
            <div className="t-chan-right">
              <span className="t-chan-time">{c.time ?? ''}</span>
              <span className="t-chan-mode">{c.mode?.toUpperCase()}</span>
            </div>
          </div>
        ))}
      </div>
    </aside>
  )
}
```

Note: channels from the backend don't include `roster` or `preview` — these will be loaded lazily when `setActive` is called. The sidebar shows empty avatar stacks initially; enhance later if needed.

- [ ] **Step 2: Create ChatHeader.jsx**

Create `frontend/src/components/chat/ChatHeader.jsx`:

```jsx
import { useNavigate } from 'react-router-dom'
import Icon, { Ico } from '../ui/Icon'
import AvatarStack from '../ui/AvatarStack'
import { useChannelStore } from '../../store/useChannelStore'
import { useThreadStore } from '../../store/useThreadStore'

export default function ChatHeader({ onExport }) {
  const navigate = useNavigate()
  const { channels, activeChannelId, roster } = useChannelStore()
  const accumulatedCost = useThreadStore((s) => s.accumulatedCost)

  const channel = channels.find((c) => c.id === activeChannelId)
  if (!channel) return <header className="t-head" />

  const costNum = parseFloat(accumulatedCost)
  const costLabel = isNaN(costNum)
    ? ''
    : `· ${costNum.toLocaleString('es', { minimumFractionDigits: 2, maximumFractionDigits: 4 })} €`

  return (
    <header className="t-head">
      <div className="t-head-title">{channel.title || 'Sin título'}</div>
      <span className="t-badge is-mode">{channel.mode === 'debate' ? 'Debate' : 'Crítica'}</span>
      <div className="t-head-roster">
        <AvatarStack
          profiles={roster}
          size={28}
          ring="color-mix(in oklab, var(--paper) 85%, var(--surface))"
        />
        <button className="t-iconbtn" title="Gestionar tertulianos" onClick={() => navigate('/profiles')}>
          <Icon d={Ico.userplus} size={18} />
        </button>
      </div>
      <div className="t-head-spacer" />
      {costLabel && <span className="t-cost">{costLabel}</span>}
      <button className="t-btn is-sm" onClick={onExport}>
        <Icon d={Ico.export} size={16} />Exportar
      </button>
    </header>
  )
}
```

- [ ] **Step 3: Commit**

```bash
cd /data/agora
git add frontend/src/components/chat/Sidebar.jsx frontend/src/components/chat/ChatHeader.jsx
git commit -m "feat: add Sidebar and ChatHeader components"
```

---

## Task 8: Thread + Message + ThinkingRow

**Files:**
- Create: `frontend/src/components/chat/Message.jsx`
- Create: `frontend/src/components/chat/ThinkingRow.jsx`
- Create: `frontend/src/components/chat/Thread.jsx`

- [ ] **Step 1: Create Message.jsx**

Create `frontend/src/components/chat/Message.jsx`:

```jsx
import Avatar from '../ui/Avatar'
import { useChannelStore } from '../../store/useChannelStore'

function renderText(text) {
  const parts = text.split(/(@\w+)/g)
  return parts.map((s, i) =>
    s.startsWith('@')
      ? <span key={i} className="t-mention">{s}</span>
      : <span key={i}>{s}</span>
  )
}

export default function Message({ message }) {
  const roster = useChannelStore((s) => s.roster)

  if (message.role === 'human') {
    return (
      <div className="t-msg is-user">
        <div className="t-bubble is-user">
          <div className="t-msg-text">{renderText(message.content)}</div>
          {message.time && <span className="t-time t-bubble-time">{message.time}</span>}
        </div>
      </div>
    )
  }

  const profile = roster.find((p) => p.profile_id === message.profileId)

  return (
    <div className="t-msg is-tert row-tint" data-voice={profile?.color ?? 'vera'}>
      <Avatar profile={profile} size={34} />
      <div className="t-msg-body">
        <div className="t-msg-head">
          <span className="t-msg-name">{profile?.name ?? '…'}</span>
          {profile?.funcion && (
            <span className="t-rolechip">· {profile.funcion.toLowerCase()}</span>
          )}
          {message.time && <span className="t-time">{message.time}</span>}
        </div>
        <div className="t-msg-text">
          {renderText(message.content)}
          {message.streaming && <span className="t-caret" />}
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Create ThinkingRow.jsx**

Create `frontend/src/components/chat/ThinkingRow.jsx`:

```jsx
import Avatar from '../ui/Avatar'
import { useChannelStore } from '../../store/useChannelStore'

export default function ThinkingRow({ profileId }) {
  const roster = useChannelStore((s) => s.roster)
  const profile = roster.find((p) => p.profile_id === profileId)

  return (
    <div className="t-msg is-tert" data-voice={profile?.color ?? 'vera'}>
      <Avatar profile={profile} size={34} />
      <div className="t-msg-body">
        <div className="t-think-typing">
          <span className="t-msg-name">{profile?.name ?? '…'}</span> está pensando
          <span className="t-dots"><i /><i /><i /></span>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Create Thread.jsx**

Create `frontend/src/components/chat/Thread.jsx`:

```jsx
import { useEffect, useRef } from 'react'
import { useThreadStore } from '../../store/useThreadStore'
import { useChannelStore } from '../../store/useChannelStore'
import Message from './Message'
import ThinkingRow from './ThinkingRow'
import AvatarStack from '../ui/AvatarStack'

function EmptyState({ roster }) {
  const starters = ['¿Qué opináis sobre esto?', '¿Por dónde empezamos?', 'Quiero debatir una idea']
  return (
    <div className="t-empty">
      <AvatarStack profiles={roster} size={40} />
      <div className="t-empty-title">Canal listo</div>
      <div className="t-empty-sub">Escribe para empezar el debate</div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'center', marginTop: 12 }}>
        {starters.map((s) => (
          <span key={s} className="t-badge" style={{ cursor: 'default' }}>{s}</span>
        ))}
      </div>
    </div>
  )
}

export default function Thread() {
  const { messages, thinking } = useThreadStore()
  const { roster, activeChannelId } = useChannelStore()
  const bottomRef = useRef(null)
  const isStreaming = thinking.size > 0 || messages.some((m) => m.streaming)

  useEffect(() => {
    if (isStreaming || messages.length === 0) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, thinking, isStreaming])

  if (!activeChannelId) {
    return (
      <div className="t-thread t-scroll">
        <div className="t-thread-inner">
          <div className="t-empty" style={{ marginTop: 80, textAlign: 'center' }}>
            <div className="t-empty-title">Selecciona un canal</div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="t-thread t-scroll">
      <div className="t-thread-inner">
        {messages.length === 0 ? (
          <EmptyState roster={roster} />
        ) : (
          <>
            <div className="t-daysep"><span>hoy</span></div>
            {messages.map((m) => <Message key={m.id} message={m} />)}
            {[...thinking].map((profileId) => (
              <ThinkingRow key={profileId} profileId={profileId} />
            ))}
          </>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Commit**

```bash
cd /data/agora
git add frontend/src/components/chat/Message.jsx \
        frontend/src/components/chat/ThinkingRow.jsx \
        frontend/src/components/chat/Thread.jsx
git commit -m "feat: add Thread, Message, ThinkingRow components"
```

---

## Task 9: Composer + MentionPopover

**Files:**
- Create: `frontend/src/components/chat/MentionPopover.jsx`
- Create: `frontend/src/components/chat/Composer.jsx`

- [ ] **Step 1: Create MentionPopover.jsx**

Create `frontend/src/components/chat/MentionPopover.jsx`:

```jsx
import { useEffect, useRef } from 'react'
import Avatar from '../ui/Avatar'

export default function MentionPopover({ profiles, filter, onSelect, onClose }) {
  const normalize = (s) =>
    s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()

  const filtered = profiles.filter((p) =>
    normalize(p.name).startsWith(normalize(filter))
  )

  const listRef = useRef(null)

  useEffect(() => {
    const handleKey = (e) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [onClose])

  if (filtered.length === 0) return null

  return (
    <div className="t-mentionpop">
      {filtered.map((p) => (
        <div
          key={p.profile_id}
          className="t-prow"
          style={{ cursor: 'pointer', padding: '8px 12px' }}
          onMouseDown={(e) => { e.preventDefault(); onSelect(p.name) }}
        >
          <Avatar profile={p} size={28} />
          <div className="t-prow-body">
            <div className="t-prow-top">
              <span className="t-prow-name" data-voice={p.color}>{p.name}</span>
              {p.funcion && <span className="t-rolechip">· {p.funcion.toLowerCase()}</span>}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 2: Create Composer.jsx**

Create `frontend/src/components/chat/Composer.jsx`:

```jsx
import { useState, useRef } from 'react'
import Icon, { Ico } from '../ui/Icon'
import MentionPopover from './MentionPopover'
import { useChannelStore } from '../../store/useChannelStore'
import { useThreadStore } from '../../store/useThreadStore'
import { streamTurn, streamRound } from '../../services/sse'

export default function Composer() {
  const [text, setText] = useState('')
  const [mentionFilter, setMentionFilter] = useState(null) // null = closed, string = filter
  const inputRef = useRef(null)

  const { activeChannelId, roster } = useChannelStore()
  const { addUserMessage, addThinking, appendToken, finalizeMessage, setCost, setError } = useThreadStore()
  const isStreaming = useThreadStore((s) => s.thinking.size > 0 || s.messages.some((m) => m.streaming))

  const handlers = {
    onStart: (profileId) => addThinking(profileId),
    onToken: (profileId, chunk) => appendToken(profileId, chunk),
    onDone: (profileId, meta) => finalizeMessage(profileId, meta),
    onComplete: (total) => setCost(total),
    onError: (msg) => setError(msg),
  }

  const handleInput = (e) => {
    const val = e.target.value
    setText(val)
    const atIdx = val.lastIndexOf('@')
    if (atIdx !== -1 && atIdx === val.length - 1) {
      setMentionFilter('')
    } else if (atIdx !== -1 && !val.slice(atIdx + 1).includes(' ')) {
      setMentionFilter(val.slice(atIdx + 1))
    } else {
      setMentionFilter(null)
    }
  }

  const selectMention = (name) => {
    const atIdx = text.lastIndexOf('@')
    setText(text.slice(0, atIdx) + '@' + name + ' ')
    setMentionFilter(null)
    inputRef.current?.focus()
  }

  const send = async () => {
    if (!text.trim() || !activeChannelId || isStreaming) return
    const content = text.trim()
    setText('')
    setMentionFilter(null)
    addUserMessage(content)
    await streamTurn(activeChannelId, content, handlers)
  }

  const handleRound = async () => {
    if (!activeChannelId || isStreaming) return
    await streamRound(activeChannelId, handlers)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div className="t-composer">
      <div className="t-composer-inner">
        <div className="t-inputbar" style={{ position: 'relative' }}>
          {mentionFilter !== null && (
            <div style={{ position: 'absolute', bottom: '100%', left: 0, zIndex: 10 }}>
              <MentionPopover
                profiles={roster}
                filter={mentionFilter}
                onSelect={selectMention}
                onClose={() => setMentionFilter(null)}
              />
            </div>
          )}
          <div className="t-input-field">
            <input
              ref={inputRef}
              value={text}
              onChange={handleInput}
              onKeyDown={handleKeyDown}
              placeholder="Escribe… usa @ para dirigirte a alguien"
              disabled={isStreaming || !activeChannelId}
              style={{
                background: 'none', border: 'none', outline: 'none',
                flex: 1, font: 'inherit', color: 'inherit', width: '100%',
              }}
            />
          </div>
          <div className="t-input-actions">
            <button
              className="t-btn is-sm is-ghost"
              onClick={handleRound}
              disabled={isStreaming || !activeChannelId}
            >
              <Icon d={Ico.round} size={16} />Otra ronda
            </button>
            <button
              className="t-sendbtn"
              onClick={send}
              disabled={!text.trim() || isStreaming || !activeChannelId}
            >
              <Icon d={Ico.send} size={18} />
            </button>
          </div>
        </div>
        <div className="t-composer-hint">
          <span className="t-kbd">@</span> menciona a un tertuliano
          <span style={{ opacity: 0.5 }}> · </span>
          <span className="t-kbd">⏎</span> enviar
          <span style={{ opacity: 0.5 }}> · </span>
          "Otra ronda" relanza sin escribir nada
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Commit**

```bash
cd /data/agora
git add frontend/src/components/chat/Composer.jsx \
        frontend/src/components/chat/MentionPopover.jsx
git commit -m "feat: add Composer with @mention popover and SSE dispatch"
```

---

## Task 10: ChatScreen assembly + ExportModal

**Files:**
- Modify: `frontend/src/screens/ChatScreen.jsx`
- Create: `frontend/src/components/export/ExportModal.jsx`

- [ ] **Step 1: Create ExportModal.jsx**

Create `frontend/src/components/export/ExportModal.jsx`:

```jsx
import Icon, { Ico } from '../ui/Icon'
import { useChannelStore } from '../../store/useChannelStore'
import { useThreadStore } from '../../store/useThreadStore'

function buildMarkdown(channel, messages, roster) {
  if (!channel) return ''
  const rosterById = Object.fromEntries(roster.map((p) => [p.profile_id, p]))
  const lines = []
  lines.push(`# ${channel.title || 'Sin título'}`)
  lines.push(`_${channel.mode === 'debate' ? 'Debate' : 'Crítica'} · ${roster.map((p) => p.name).join(', ')} · Agora_`)
  lines.push('')
  for (const m of messages) {
    if (m.role === 'human') {
      lines.push(`**Tú** · ${m.time ?? ''}`)
    } else {
      const p = rosterById[m.profileId]
      lines.push(`**${p?.name ?? '?'}** _(${p?.funcion?.toLowerCase() ?? ''})_ · ${m.time ?? ''}`)
    }
    lines.push('')
    lines.push(m.content)
    lines.push('')
    lines.push('---')
    lines.push('')
  }
  return lines.join('\n')
}

export default function ExportModal({ onClose }) {
  const { channels, activeChannelId, roster } = useChannelStore()
  const messages = useThreadStore((s) => s.messages)
  const channel = channels.find((c) => c.id === activeChannelId)
  const md = buildMarkdown(channel, messages, roster)

  const copy = () => navigator.clipboard.writeText(md)

  return (
    <div className="t-modal-backdrop" onClick={onClose}>
      <div className="t-modal" onClick={(e) => e.stopPropagation()}>
        <div className="t-modal-head">
          <div>
            <div className="t-sheet-eyebrow">Exportar conversación</div>
            <div className="t-modal-title">Markdown</div>
          </div>
          <div className="t-head-spacer" />
          <button className="t-iconbtn" onClick={onClose}>✕</button>
        </div>
        <div className="t-modal-bar">
          <span className="t-modal-hint">Texto sin formato · pégalo donde quieras</span>
          <div className="t-head-spacer" />
          <button className="t-btn is-sm is-primary" onClick={copy}>
            <Icon d={Ico.copy} size={15} />Copiar
          </button>
        </div>
        <div className="t-modal-body t-scroll">
          <pre className="t-md">{md}</pre>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Replace ChatScreen stub**

Replace `frontend/src/screens/ChatScreen.jsx`:

```jsx
import { useState } from 'react'
import Sidebar from '../components/chat/Sidebar'
import ChatHeader from '../components/chat/ChatHeader'
import Thread from '../components/chat/Thread'
import Composer from '../components/chat/Composer'
import ExportModal from '../components/export/ExportModal'
import { useThreadStore } from '../store/useThreadStore'

export default function ChatScreen() {
  const [showExport, setShowExport] = useState(false)
  const error = useThreadStore((s) => s.error)
  const clearError = useThreadStore((s) => s.clearError)

  return (
    <div className="t-app">
      <Sidebar />
      <main className="t-main">
        <ChatHeader onExport={() => setShowExport(true)} />
        {error && (
          <div className="t-error">
            <span>{error}</span>
            <button className="t-btn is-sm" onClick={clearError}>Reintentar</button>
          </div>
        )}
        <Thread />
        <Composer />
      </main>
      {showExport && <ExportModal onClose={() => setShowExport(false)} />}
    </div>
  )
}
```

- [ ] **Step 3: Smoke-test the chat screen**

Start backend and frontend:

```bash
cd /data/agora && source .venv/bin/activate
uvicorn backend.main:app --host 127.0.0.1 --port 8001 &
cd frontend && npm run dev
```

Open `http://localhost:5173`. Verify:
- Sidebar shows "Agora." wordmark and "Nuevo canal" button
- If channels exist in DB, they appear in the list
- Selecting a channel loads messages in the thread
- Theme toggle switches to dark mode

- [ ] **Step 4: Commit**

```bash
cd /data/agora
git add frontend/src/screens/ChatScreen.jsx \
        frontend/src/components/export/ExportModal.jsx
git commit -m "feat: assemble ChatScreen with thread, composer, export modal"
```

---

## Task 11: CreateScreen

**Files:**
- Modify: `frontend/src/screens/CreateScreen.jsx`

- [ ] **Step 1: Replace CreateScreen stub**

Replace `frontend/src/screens/CreateScreen.jsx`:

```jsx
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Icon, { Ico } from '../components/ui/Icon'
import Avatar from '../components/ui/Avatar'
import { getProfiles, createChannel, addToRoster } from '../services/api'
import { useChannelStore } from '../store/useChannelStore'

function ModeCard({ active, title, desc, onClick }) {
  return (
    <div className={`t-modecard${active ? ' is-on' : ''}`} onClick={onClick} style={{ cursor: 'pointer' }}>
      <div className="t-modecard-t"><span className="t-modedot" />{title}</div>
      <div className="t-modecard-d">{desc}</div>
    </div>
  )
}

export default function CreateScreen() {
  const navigate = useNavigate()
  const { addChannel, setActive } = useChannelStore()

  const [title, setTitle] = useState('')
  const [mode, setMode] = useState('debate')
  const [profiles, setProfiles] = useState([])
  const [selected, setSelected] = useState(new Set())
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    getProfiles().then((ps) => setProfiles(ps.filter((p) => !p.archived)))
  }, [])

  const toggle = (id) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else if (next.size < 3) next.add(id)
      return next
    })
  }

  const full = selected.size >= 3

  const handleCreate = async () => {
    if (selected.size === 0 || saving) return
    setSaving(true)
    try {
      const channel = await createChannel({ title: title || 'Sin título', mode })
      let order = 0
      for (const profileId of selected) {
        await addToRoster(channel.id, { profile_id: profileId, speaking_order: order++ })
      }
      addChannel(channel)
      await setActive(channel.id)
      navigate('/')
    } catch (err) {
      console.error(err)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="t-sheet">
      <div className="t-sheet-head">
        <div>
          <div className="t-sheet-eyebrow">Nuevo canal</div>
          <div className="t-sheet-title">¿De qué hablamos?</div>
        </div>
        <div className="t-head-spacer" />
        <button className="t-iconbtn" onClick={() => navigate('/')}>✕</button>
      </div>

      <div className="t-sheet-body t-scroll">
        <div className="t-sheet-inner">
          <div>
            <div className="t-field-label">Título del canal</div>
            <input
              className="t-titlefield"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Newsletter de urbanismo…"
              style={{ display: 'block', width: '100%', background: 'none', border: 'none', outline: 'none', font: 'inherit', color: 'inherit' }}
            />
          </div>

          <div>
            <div className="t-field-label">Modo</div>
            <div className="t-modeseg">
              <ModeCard
                active={mode === 'debate'} title="Debate"
                desc="Para discutir una idea: los tertulianos la tensan entre todos."
                onClick={() => setMode('debate')}
              />
              <ModeCard
                active={mode === 'critica'} title="Crítica"
                desc="Para revisar un texto: lo leen y te lo devuelven con notas."
                onClick={() => setMode('critica')}
              />
            </div>
          </div>

          <div>
            <div className="t-pickhead">
              <div className="t-field-label" style={{ margin: 0 }}>Tertulianos · elige 1–3</div>
              <span className={`t-pickcount${full ? ' is-full' : ''}`}>
                {selected.size} / 3{full ? ' · completo' : ''}
              </span>
            </div>
            <div className="t-picklist">
              {profiles.map((p) => {
                const isSel = selected.has(p.id)
                const dim = full && !isSel
                return (
                  <div
                    key={p.id}
                    className={`t-prow${isSel ? ' is-sel' : ''}${dim ? ' is-dim' : ''}`}
                    onClick={() => toggle(p.id)}
                    style={{ cursor: dim ? 'default' : 'pointer' }}
                  >
                    <Avatar profile={p} size={38} />
                    <div className="t-prow-body">
                      <div className="t-prow-top">
                        <span className="t-prow-name" data-voice={p.color}>{p.name}</span>
                        {p.funcion && <span className="t-rolechip">· {p.funcion.toLowerCase()}</span>}
                        {p.tipo === 'facilitador' && <span className="t-tag-fac">facilitador</span>}
                      </div>
                    </div>
                    <div className={`t-check${isSel ? ' is-on' : ''}`}>
                      <Icon d={Ico.check} size={13} stroke={2} />
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </div>

      <div className="t-sheet-foot">
        <button className="t-btn is-ghost" onClick={() => navigate('/')}>Cancelar</button>
        <button
          className="t-btn is-primary"
          onClick={handleCreate}
          disabled={selected.size === 0 || saving}
        >
          {saving ? 'Creando…' : 'Abrir canal'}
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Test the create flow**

Open `http://localhost:5173/channels/new`. Verify:
- Profile list loads from backend
- Selecting profiles shows check + counter
- At 3 profiles selected, unselected ones dim
- "Abrir canal" creates the channel, navigates to chat, starts loading

- [ ] **Step 3: Commit**

```bash
cd /data/agora
git add frontend/src/screens/CreateScreen.jsx
git commit -m "feat: implement CreateScreen with channel + roster creation"
```

---

## Task 12: EditorScreen

**Files:**
- Modify: `frontend/src/screens/EditorScreen.jsx`

- [ ] **Step 1: Replace EditorScreen stub**

Replace `frontend/src/screens/EditorScreen.jsx`:

```jsx
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Icon, { Ico } from '../components/ui/Icon'
import Avatar from '../components/ui/Avatar'
import { getProfiles, patchProfile, createProfile, deleteProfile } from '../services/api'

const MODEL_LABELS = {
  'claude-sonnet-4-6': 'Claude Sonnet',
  'claude-opus-4-8': 'Claude Opus',
  'claude-haiku-4-5-20251001': 'Claude Haiku',
}
const MODEL_IDS = Object.keys(MODEL_LABELS)

function VoiceSwatch({ id, on, onClick }) {
  return (
    <button className={`t-voicesw${on ? ' is-on' : ''}`} data-voice={id} onClick={onClick} aria-label={id}>
      <span className="t-voicesw-dot" />
    </button>
  )
}

function SegBtn({ on, children, onClick }) {
  return <button className={`t-seg-btn${on ? ' is-on' : ''}`} onClick={onClick}>{children}</button>
}

function TempSlider({ value, onChange }) {
  const pct = Math.round(value * 100)
  const label = value <= 0.4 ? 'centrada' : value >= 0.75 ? 'imprevisible' : 'equilibrada'
  return (
    <div className="t-temp">
      <div className="t-temp-track" style={{ position: 'relative' }}>
        <div className="t-temp-fill" style={{ width: pct + '%' }} />
        <div className="t-temp-knob" style={{ left: pct + '%' }} />
        <input
          type="range" min="0" max="1" step="0.05" value={value}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          style={{ position: 'absolute', inset: 0, opacity: 0, cursor: 'pointer', width: '100%' }}
        />
      </div>
      <div className="t-temp-foot">
        <span>centrada</span>
        <span className="t-temp-val">{value.toFixed(2)} · {label}</span>
        <span>creativa</span>
      </div>
    </div>
  )
}

const EMPTY = { name: '', funcion: '', tipo: 'tertuliano', color: 'vera', model: 'claude-sonnet-4-6', temperature: 0.7, system_prompt: '' }

export default function EditorScreen() {
  const navigate = useNavigate()
  const [profiles, setProfiles] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    getProfiles().then((ps) => {
      const active = ps.filter((p) => !p.archived)
      setProfiles(active)
      if (active.length > 0) select(active[0])
    })
  }, [])

  const select = (p) => {
    setActiveId(p.id)
    setForm({
      name: p.name,
      funcion: p.funcion,
      tipo: p.tipo,
      color: p.color ?? 'vera',
      model: p.model,
      temperature: p.temperature,
      system_prompt: p.system_prompt,
    })
    setDirty(false)
  }

  const set = (key, val) => { setForm((f) => ({ ...f, [key]: val })); setDirty(true) }

  const save = async () => {
    if (!dirty || saving) return
    setSaving(true)
    try {
      if (activeId === 'new') {
        const created = await createProfile(form)
        setProfiles((ps) => [...ps, created])
        select(created)
      } else {
        const updated = await patchProfile(activeId, form)
        setProfiles((ps) => ps.map((p) => (p.id === activeId ? updated : p)))
        setDirty(false)
      }
    } finally {
      setSaving(false)
    }
  }

  const remove = async () => {
    if (!activeId || activeId === 'new') return
    if (!confirm(`¿Eliminar a ${form.name}?`)) return
    await deleteProfile(activeId)
    const remaining = profiles.filter((p) => p.id !== activeId)
    setProfiles(remaining)
    if (remaining.length > 0) select(remaining[0])
    else { setActiveId(null); setForm(EMPTY) }
  }

  const newProfile = () => {
    setActiveId('new')
    setForm(EMPTY)
    setDirty(false)
  }

  const active = profiles.find((p) => p.id === activeId)

  return (
    <div className="t-editor">
      <div className="t-ed-list">
        <div className="t-ed-list-head">
          <div className="t-sheet-eyebrow">Tertulianos</div>
          <button className="t-iconbtn" onClick={newProfile}><Icon d={Ico.plus} size={17} /></button>
        </div>
        <div className="t-ed-list-scroll t-scroll">
          {profiles.map((p) => (
            <div
              key={p.id}
              className={`t-ed-litem${p.id === activeId ? ' is-active' : ''}`}
              onClick={() => select(p)}
              style={{ cursor: 'pointer' }}
            >
              <Avatar profile={p} size={34} />
              <div style={{ minWidth: 0, flex: 1 }}>
                <div className="t-ed-litem-name" data-voice={p.color}>{p.name}</div>
                <div className="t-ed-litem-role">{p.funcion?.toLowerCase()}</div>
              </div>
              {p.tipo === 'facilitador' && <span className="t-tag-fac">fac.</span>}
            </div>
          ))}
        </div>
        <div className="t-ed-list-foot">
          <button className="t-btn is-sm is-ghost" onClick={() => navigate('/')}>
            ← Volver al chat
          </button>
        </div>
      </div>

      {activeId && (
        <div className="t-ed-form">
          <div className="t-ed-form-head">
            <Avatar profile={activeId === 'new' ? { name: form.name || '?', color: form.color } : active} size={44} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="t-ed-form-title" data-voice={form.color}>{form.name || 'Nuevo perfil'}</div>
              <div className="t-rolechip">{form.funcion?.toLowerCase()} · {MODEL_LABELS[form.model] ?? form.model}</div>
            </div>
            <button className="t-btn is-sm" onClick={save} disabled={!dirty || saving}>
              {saving ? 'Guardando…' : 'Guardar'}
            </button>
          </div>

          <div className="t-ed-form-body t-scroll">
            <div className="t-ed-grid">
              <div className="t-fld" style={{ gridColumn: 'span 7' }}>
                <div className="t-field-label">Nombre</div>
                <input className="t-input" value={form.name} onChange={(e) => set('name', e.target.value)}
                  style={{ display: 'block', width: '100%', background: 'none', border: 'none', outline: 'none', font: 'inherit', color: 'inherit' }} />
              </div>
              <div className="t-fld" style={{ gridColumn: 'span 5' }}>
                <div className="t-field-label">Papel en la mesa</div>
                <div className="t-seg">
                  <SegBtn on={form.tipo === 'tertuliano'} onClick={() => set('tipo', 'tertuliano')}>Tertuliano</SegBtn>
                  <SegBtn on={form.tipo === 'facilitador'} onClick={() => set('tipo', 'facilitador')}>Facilitador</SegBtn>
                </div>
              </div>

              <div className="t-fld" style={{ gridColumn: 'span 12' }}>
                <div className="t-field-label">Función · cómo se le presenta</div>
                <input className="t-input" value={form.funcion} onChange={(e) => set('funcion', e.target.value)}
                  style={{ display: 'block', width: '100%', background: 'none', border: 'none', outline: 'none', font: 'inherit', color: 'inherit' }} />
              </div>

              <div className="t-fld" style={{ gridColumn: 'span 12' }}>
                <div className="t-field-label">Color de voz</div>
                <div className="t-voicerow">
                  {['vera', 'bruno', 'iris'].map((v) => (
                    <VoiceSwatch key={v} id={v} on={form.color === v} onClick={() => set('color', v)} />
                  ))}
                  <span className="t-voicerow-note">El color identifica a {form.name || 'este perfil'} en el chat.</span>
                </div>
              </div>

              <div className="t-fld" style={{ gridColumn: 'span 6' }}>
                <div className="t-field-label">Modelo</div>
                <select
                  className="t-select"
                  value={form.model}
                  onChange={(e) => set('model', e.target.value)}
                  style={{ width: '100%', background: 'none', border: 'none', outline: 'none', font: 'inherit', color: 'inherit', cursor: 'pointer' }}
                >
                  {MODEL_IDS.map((id) => <option key={id} value={id}>{MODEL_LABELS[id]}</option>)}
                </select>
                <div className="t-fld-hint">Opus razona más hondo · Sonnet va más rápido</div>
              </div>

              <div className="t-fld" style={{ gridColumn: 'span 6' }}>
                <div className="t-field-label">Temperatura</div>
                <TempSlider value={form.temperature} onChange={(v) => set('temperature', v)} />
              </div>

              <div className="t-fld" style={{ gridColumn: 'span 12' }}>
                <div className="t-field-label">Cómo piensa · system prompt</div>
                <textarea
                  className="t-textarea"
                  value={form.system_prompt}
                  onChange={(e) => set('system_prompt', e.target.value)}
                  rows={8}
                  style={{ display: 'block', width: '100%', background: 'none', border: 'none', outline: 'none', font: 'inherit', color: 'inherit', resize: 'vertical' }}
                />
              </div>
            </div>
          </div>

          <div className="t-ed-form-foot">
            {activeId !== 'new' && (
              <button className="t-btn is-sm is-ghost" style={{ color: 'var(--warn)' }} onClick={remove}>
                Eliminar perfil
              </button>
            )}
            <div className="t-head-spacer" />
            {dirty && <span className="t-cost">cambios sin guardar</span>}
            <button className="t-btn is-sm is-ghost" onClick={() => { if (active) select(active); else { setActiveId(null); setForm(EMPTY) } }}>
              Descartar
            </button>
            <button className="t-btn is-sm is-primary" onClick={save} disabled={!dirty || saving}>
              {saving ? 'Guardando…' : 'Guardar cambios'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Test the editor**

Open `http://localhost:5173/profiles`. Verify:
- Profile list loads
- Selecting a profile fills the form
- Editing name updates the header preview in real time
- Voice swatch changes the color
- Temp slider moves
- Saving patches the backend (check with `curl http://localhost:8001/profiles/1`)
- "Nuevo perfil" opens a blank form; saving creates a new profile

- [ ] **Step 3: Commit**

```bash
cd /data/agora
git add frontend/src/screens/EditorScreen.jsx
git commit -m "feat: implement EditorScreen with full profile CRUD"
```

---

## Task 13: Mobile layout verification + nginx config

**Files:**
- Create: `frontend/nginx.conf` (production config)
- Verify: mobile CSS already ported in Task 2

The CSS files ported in Task 2 already contain the mobile media queries for ≤412px. This task verifies they work and creates the production nginx config.

- [ ] **Step 1: Test mobile layout in browser**

In Chrome DevTools, set device to "Samsung Galaxy S20 Ultra" (412×915) or use:

Responsive mode → 412px width.

Verify:
- Sidebar hides below 500px breakpoint (check `tertulia-mobile.css` for the exact breakpoint)
- Thread fills full width
- Composer stacks correctly
- Font sizes remain readable

If the mobile CSS breakpoint in `tertulia-mobile.css` targets 402px (iPhone), update the selector:

```bash
grep -n "402\|412\|mobile\|@media" /data/agora/frontend/src/styles/tertulia-mobile.css | head -20
```

If `402` appears, update to `412`:

```bash
sed -i 's/max-width: 402px/max-width: 412px/g' /data/agora/frontend/src/styles/tertulia-mobile.css
```

- [ ] **Step 2: Build production bundle**

```bash
cd /data/agora/frontend && npm run build
ls -lh dist/
```

Expected: `dist/index.html` + `dist/assets/` with hashed JS/CSS files.

- [ ] **Step 3: Create nginx config**

Create `frontend/nginx.conf`:

```nginx
server {
    listen 5151;
    server_name _;
    root /data/agora/frontend/dist;
    index index.html;

    gzip on;
    gzip_types text/css application/javascript application/json;

    location /api/ {
        proxy_pass http://127.0.0.1:8001/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;

        # SSE support
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding on;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

- [ ] **Step 4: Commit**

```bash
cd /data/agora
git add frontend/nginx.conf frontend/src/styles/tertulia-mobile.css
git commit -m "feat: add nginx prod config and verify mobile layout at 412px"
```

---

## Task 14: End-to-end smoke test

No new files — this task verifies the full golden path works.

- [ ] **Step 1: Start backend**

```bash
cd /data/agora && source .venv/bin/activate
uvicorn backend.main:app --host 127.0.0.1 --port 8001
```

- [ ] **Step 2: Start frontend dev server**

```bash
cd /data/agora/frontend && npm run dev
```

Open `http://localhost:5173`.

- [ ] **Step 3: Golden path test**

Execute in order and verify each step:

1. **Create a profile** — navigate to `/profiles`, click "Nuevo perfil", fill name "Vera", función "La escéptica", voice swatch "vera", model Sonnet, temp 0.7, add a system prompt, save. Verify it appears in the list.

2. **Create a channel** — click "Nuevo canal", title "Test debate", mode Debate, select Vera, click "Abrir canal". Verify redirect to chat with Vera in the header roster.

3. **Send a message** — type "¿Qué opinas sobre el software de IA?" and press Enter. Verify:
   - Your message appears right-aligned
   - "Vera está pensando…" appears
   - Tokens stream in with a blinking caret
   - Message finalizes with timestamp and cost

4. **Otra ronda** — click "Otra ronda". Verify Vera responds again without a new human message.

5. **@mention** — type "@Ve" in the composer. Verify MentionPopover appears with Vera. Press Enter or click to insert `@Vera`. Send. Verify Vera responds.

6. **Export** — click Exportar in the header. Verify modal shows Markdown with the conversation. Click Copiar — paste in a text editor to confirm.

7. **Dark mode** — click the sun/moon toggle. Verify the entire UI switches to dark theme and persists on refresh.

- [ ] **Step 4: Run all frontend tests**

```bash
cd /data/agora/frontend && npx vitest run 2>&1 | tail -20
```

Expected: PASS all (store tests + SSE parser tests).

- [ ] **Step 5: Run backend tests**

```bash
cd /data/agora && source .venv/bin/activate
pytest backend/tests/ -v 2>&1 | tail -30
```

Expected: PASS all.

- [ ] **Step 6: Final commit**

```bash
cd /data/agora
git add -p  # stage only intentional changes
git commit -m "feat: Agora Fase 3 — React frontend complete"
```
