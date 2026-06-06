# Spec: Agora — Frontend React (Fase 3)

## Contexto

El backend de Agora está completo (Fase 2B): FastAPI + SSE streaming, compresión de contexto, @mención, endpoint `/rounds`. Esta spec cubre el frontend React que lo conecta, reproduciendo con alta fidelidad el diseño entregado en `docs-disenio/design_frontend_handoff_agora/`.

**Gap de backend a resolver en Fase 3 (Tarea 1):** No existe `GET /channels/{id}/messages` — el frontend lo necesita para cargar el historial al cambiar de canal. Hay que añadirlo antes de implementar las stores.

---

## Stack decidido

| Capa | Decisión |
|---|---|
| Framework | React 18 + Vite |
| Estilos | CSS vars del diseño portadas a `src/styles/` + Tailwind v3 para utilidades de layout |
| Estado global | Zustand (3 stores) |
| Routing | React Router DOM v6 |
| Fuentes | Google Fonts: Newsreader + Hanken Grotesk + JetBrains Mono |
| Testing | Vitest |
| Dev proxy | `/api → http://localhost:8001` (Vite config) |
| Puertos prod | uvicorn :8001 (loopback), nginx :5151 (Tailscale) |

Sin TypeScript. Sin dependencias adicionales más allá de las listadas.

---

## Arquitectura

### Routing (React Router DOM v6)

| Ruta | Componente | Notas |
|---|---|---|
| `/` | `ChatScreen` | Vista principal; empty state si no hay canal activo |
| `/channels/new` | `CreateScreen` | Full-screen sheet sobre el chat |
| `/profiles` | `EditorScreen` | Grid lista + formulario |

### Estructura de ficheros

```
frontend/
├── index.html              ← link Google Fonts, div#root
├── vite.config.js          ← proxy /api → localhost:8001
├── tailwind.config.js
└── src/
    ├── main.jsx
    ├── App.jsx             ← Router root, aplica .t-dark a <html>
    │
    ├── styles/
    │   ├── tertulia.css            ← tokens oklch + átomos (portado tal cual)
    │   ├── tertulia-screens.css    ← layouts desktop (portado tal cual)
    │   └── tertulia-mobile.css     ← ajustes ≤412px (portado tal cual)
    │
    ├── screens/
    │   ├── ChatScreen.jsx
    │   ├── CreateScreen.jsx
    │   └── EditorScreen.jsx
    │
    ├── components/
    │   ├── ui/
    │   │   ├── Avatar.jsx          ← inicial + aro data-voice
    │   │   ├── AvatarStack.jsx
    │   │   └── Icon.jsx            ← SVGs inline (plus, search, sun, moon, send, export, round…)
    │   ├── chat/
    │   │   ├── Sidebar.jsx         ← lista canales + buscador + botón nuevo
    │   │   ├── ChatHeader.jsx      ← título, modo, roster, coste, export
    │   │   ├── Thread.jsx          ← scroll container + empty state
    │   │   ├── Message.jsx         ← burbuja usuario / burbuja teñida / streaming con caret
    │   │   ├── ThinkingRow.jsx     ← "{Nombre} está pensando…" variante B
    │   │   ├── Composer.jsx        ← input, botón "Otra ronda", botón enviar
    │   │   └── MentionPopover.jsx  ← lista filtrada de tertulianos del canal
    │   └── export/
    │       └── ExportModal.jsx     ← modal desktop / bottom sheet móvil
    │
    ├── store/
    │   ├── useAppStore.js      ← { theme, toggleTheme } — persist localStorage
    │   ├── useChannelStore.js  ← { channels, activeChannelId, roster, fetchChannels, setActive }
    │   └── useThreadStore.js   ← { messages, thinking, accumulatedCost, addThinking,
    │                               appendToken, finalizeMessage, setCost, addUserMessage }
    │
    └── services/
        ├── api.js   ← fetch REST: GET/POST channels, profiles, roster
        └── sse.js   ← fetch POST stream + parser SSE → despacha al threadStore
```

---

## Estado (Zustand stores)

### `useAppStore`
```js
{
  theme: 'light' | 'dark',
  toggleTheme: () => void,
}
```
Persiste en `localStorage`. App.jsx añade/quita clase `.t-dark` en `<html>` al cambiar.

### `useChannelStore`
```js
{
  channels: Channel[],
  activeChannelId: number | null,
  roster: Profile[],            // tertulianos del canal activo
  fetchChannels: () => Promise,
  setActive: (id) => Promise,   // carga roster + historial de mensajes del canal
}
```
`setActive` llama en paralelo a `GET /channels/{id}/profiles` (roster) y `GET /channels/{id}/messages` (historial), luego puebla `useThreadStore`.

### `useThreadStore`
```js
{
  messages: Message[],          // { id, role, profileId, content, streaming, cost, time }
  thinking: Set<number>,        // profileIds con indicador "pensando"
  accumulatedCost: string,      // formato "0,18 €"

  addUserMessage: (content) => void,
  addThinking: (profileId) => void,
  appendToken: (profileId, chunk) => void,   // crea msg streaming o append
  finalizeMessage: (profileId, meta) => void, // fija hora, cost; quita de thinking
  setCost: (total) => void,
  setError: (msg) => void,
  clearError: () => void,
}
```

---

## SSE Streaming

El backend usa `POST` con `Content-Type: text/event-stream`. No se puede usar `EventSource` (solo GET). Implementación en `sse.js`:

```
fetch(POST /api/channels/{id}/messages, { content })
  → response.body.getReader()
  → loop: read() → TextDecoder → split por "\n\n"
    → líneas "data: {json}" → JSON.parse
    → switch(event.type):
        'start'         → addThinking(profileId)
        'token'         → appendToken(profileId, chunk)
        'done'          → finalizeMessage(profileId, { tokensIn, tokensOut, costUsd })
        'TURN_COMPLETE' → setCost(totalCost)
  → catch → setError("Error de conexión. ¿Reintentar?")
```

Mismo flujo para `POST /api/channels/{id}/rounds` (botón "Otra ronda").

---

## Pantallas

### Chat (`/`)
- Grid 2 columnas: sidebar 304px + hilo `1fr`
- **Sidebar:** logo "Agora." (`.` terracota), toggle tema, botón "Nuevo canal" (→ `/channels/new`), buscador, lista de canales con AvatarStack
- **Header:** título serif + badge modo + roster + botón "gestionar tertulianos" (→ `/profiles`, editor global de perfiles) + coste mono + botón exportar
- **Thread:** separador día, mensajes, ThinkingRow al final; auto-scroll: siempre durante streaming, solo si el usuario está al fondo al recibir nuevo mensaje
- **Message:** usuario → burbuja derecha `--user-bubble`; tertuliano → burbuja teñida (`.row-tint`, fondo `--vt`, esquina sup-izq recortada); mensaje streaming lleva caret parpadeante `.t-caret` del color de voz
- **Composer:** input con placeholder "Escribe… usa @ para dirigirte a alguien", botón fantasma "Otra ronda", botón primario enviar; hint `@ ⏎`
- **Empty state:** cuando no hay mensajes — AvatarStack, título serif, chips de sugerencia de arranque

### Crear canal (`/channels/new`)
Full-screen sheet (`.t-sheet`) centrada a 600px:
1. Input título (serif grande)
2. Picker de modo — 2 tarjetas Debate / Crítica
3. Lista de tertulianos (1–3): avatar + nombre en color voz + sub + check circular; al llegar a 3 las demás se atenúan
4. Footer: "Cancelar" + "Crear canal" (primario, deshabilitado si 0 seleccionados)

Tras crear → navegar a `/` con el nuevo canal activo.

### Editor de perfiles (`/profiles`)
Grid 264px + 1fr:
- Lista de perfiles con avatar + nombre + rol; activo resaltado; botón "Nuevo"
- Formulario: nombre, función/rol, 3 swatches de voz (`data-voice`), select modelo, slider temperatura (con valor mono), textarea prompt, segmentado tipo (tertuliano/facilitador)
- Guardar → PATCH `/api/profiles/{id}`; Nuevo → POST `/api/profiles`

### Export modal
- Desktop: modal centrado 620px con backdrop
- Móvil: bottom sheet
- Contenido: hilo convertido a Markdown (encabezados por hablante, timestamps)
- Botón copiar → `navigator.clipboard.writeText()`

---

## @mención

En `Composer`, al detectar `@` seguido de texto:
1. Filtrar `roster[]` por nombre (case + accent insensitive, igual que el backend)
2. Mostrar `MentionPopover` (320px) con lista de tertulianos del canal
3. Flechas ↑↓ + Enter para seleccionar; Escape para cerrar
4. Seleccionar inserta `@Nombre` en el input (nombres son CamelCase, sin espacios)
5. Popover se cierra al enviar o al borrar el `@`

El texto `@Nombre` en mensajes se renderiza en el color de voz del hablante, peso 600 (función `renderText` portada de `tertulia-ui.jsx`).

---

## Diseño visual

### Mecanismo de voz
Atributo `data-voice="vera|bruno|iris"` en el contenedor de cada mensaje expone `--vc` (color) y `--vt` (tinte). Avatar, nombre del hablante y caret de streaming leen `var(--vc)`. No se cablean colores por componente.

### Mobile (≤412px, Galaxy Note/Realme GT)
- Sidebar oculta → lista de canales es pantalla propia (navigation stack)
- Editor se apila verticalmente (sin grid)
- Export es bottom sheet
- Los 3 CSS files del diseño contemplan estos breakpoints

### Tema oscuro
Toggle sol/luna en sidebar. Clase `.t-dark` en `<html>` activa el bloque `.t.t-dark` del CSS (papel ~0.228 oklch, voces subidas a ~0.75 luminancia). Persiste en localStorage vía `useAppStore`.

---

## Error handling

| Situación | Comportamiento |
|---|---|
| Error de API (REST) | Toast/banda roja `.t-error` con mensaje + botón "Reintentar" |
| Error SSE durante streaming | Banda de error; mensaje parcial marcado como fallido |
| Canal no encontrado | Redirección a `/` con empty state |
| 0 tertulianos en roster | Empty state "Añade tertulianos a este canal" (sin bloqueo de composer) |

---

## Testing (Vitest)

- `useThreadStore`: appendToken acumula correctamente, finalizeMessage limpia thinking, addThinking añade al Set
- `sse.js`: parser SSE convierte chunks de texto a eventos correctamente (incluso chunks partidos)
- `useAppStore`: toggleTheme alterna y persiste
- `MentionPopover`: filtra roster correctamente con variaciones de acento y case
