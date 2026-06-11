# Mecanismo de contexto en Agora

Cómo cada tertuliano sabe lo que se ha dicho, cómo funciona la compresión y cómo se construyen los dos prompts que recibe cada perfil.

---

## 1. Estructura de la llamada a la API

Cada llamada a Anthropic tiene dos partes:

```
system  → quién eres (andamio + prompt personal)
user    → qué se ha dicho (transcripción completa como un solo bloque de texto)
```

No hay multi-turn real (`assistant` messages). Todo el historial va como **un único mensaje `user`** con el transcript pegado.

---

## 2. El andamio genérico (`andamio.py`)

Hay dos textos fijos según el modo del canal:

- **`ANDAMIO_DEBATE`** — reglas de comportamiento en una tertulia de ideas
- **`ANDAMIO_CRITICA`** — reglas para crítica de texto

La matriz de composición (`build_context`) es:

| Tipo de perfil | Modo del canal | System prompt resultante |
|---|---|---|
| `tertuliano` | `debate` | `ANDAMIO_DEBATE` + `\n\n` + `system_prompt` del perfil |
| `tertuliano` | `critica` | `ANDAMIO_CRITICA` + `\n\n` + `system_prompt` del perfil |
| `facilitador` | cualquiera | solo `system_prompt` del perfil (sin andamio) |

El `system_prompt` personal del perfil es lo que diferencia a Sócrates de Tío Gilito.

---

## 3. La transcripción como contexto (`build_context`)

El bloque `user` se construye así:

```
[Resumen de la conversación anterior]     ← si hay summary
...texto del resumen...
[Fin del resumen]

Josem: hola, hablemos de libertad
Sócrates: la libertad verdadera es...
Tío Gilito: eso es un lujo que no me puedo permitir
Josem: ...
```

Cada hablante etiquetado por nombre. Los mensajes `system` (internos) se omiten. Esto permite que el modelo sepa **quién dijo cada cosa**, incluyendo las respuestas de los tertulianos anteriores del **mismo turno** — porque en el round-robin, el segundo tertuliano ya tiene en su contexto la respuesta del primero (está guardada en DB antes de llamar al siguiente).

---

## 4. El mecanismo de compresión — acta viva (`compressor.py`)

**Umbral:** antes de cada turno, `maybe_compress` cuenta cuántos mensajes hay **después del último resumen**. Si son ≥ 30, comprime los 20 más antiguos de ese tramo.

**Modelo:** Haiku (`claude-haiku-4-5-20251001`), `temperature=0.2`, `max_tokens=1200`.

### Acta viva — la pieza clave

En lugar de generar un resumen neutro del chunk, el compresor mantiene un **acta viva**: un documento estructurado que se actualiza en cada compresión incorporando los mensajes nuevos.

Haiku recibe dos inputs delimitados:

```
<acta_anterior>
...contenido del último summary...        ← puede estar vacío (primera compresión)
</acta_anterior>

<mensajes_nuevos>
Josem: ...
Sócrates: ...
</mensajes_nuevos>
```

Y devuelve **el acta completa actualizada** — nunca un delta. La instrucción crítica al modelo: *conserva todas las entradas del acta anterior salvo que los mensajes nuevos las modifiquen, las resuelvan o las vuelvan irrelevantes.*

### Formato del acta según modo de canal

**Modo `debate`:**
```
## Tema y arranque
## Posiciones por hablante
## Desacuerdos abiertos
## Concesiones y giros
## Temas cerrados
## Datos y referencias clave
```

**Modo `critica`:**
```
## Texto y objetivo
## Observaciones por crítico
## Sugerencias sobre la mesa
## Decisiones del autor
## Fragmentos clave citados
```

### Cadena de actas

```
Compresión 1:  (sin acta previa) + msgs[1–20]   → acta_1  (cubre hasta msg 20)
Compresión 2:  acta_1           + msgs[21–40]   → acta_2  (cubre hasta msg 40)
Compresión 3:  acta_2           + msgs[41–60]   → acta_3  (cubre hasta msg 60)
```

Cada acta es **autocontenida**: incluye todo lo relevante de las anteriores. `build_context` no cambia — sigue recuperando solo el último summary, que ahora es el acta vigente.

### Fail-open

Si Haiku falla (error API, timeout, respuesta vacía) el turno **continúa sin comprimir** — se loguea el error y el próximo turno reintentará la compresión de forma natural.

---

## 5. El flujo completo de un turno (`orchestrator.py`)

```
usuario escribe
    ↓
get_channel()             ← necesario para pasar el mode al compresor
    ↓
maybe_compress(channel_id, mode)   ← actualiza el acta si toca; fail-open
    ↓
insert_message(human)     ← guarda el mensaje del usuario
    ↓
for profile in speakers:  ← round-robin (o @mención)
    summary = get_latest_summary()
    messages = get_context_messages(after=summary.covers_up_to)
    system, api_msgs = build_context(profile, channel, messages, names, summary)
    stream_turn(system, api_msgs, model, temperature)   ← llamada API
    insert_message(persona, ...)   ← guarda respuesta
    yield SSE events
```

El punto clave del round-robin: **cada tertuliano ve las respuestas de los anteriores del mismo turno** porque se guardan en DB antes de construir el contexto del siguiente.

---

## Limitaciones conocidas

- No hay multi-turn real: el modelo no "recuerda" — recibe el transcript completo cada vez.
- El acta es única por canal, no por perfil — todos los tertulianos ven el mismo acta.
- Umbral de compresión en número de mensajes (no tokens) — mejora futura.
