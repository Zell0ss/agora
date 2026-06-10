import json
from collections.abc import AsyncGenerator
from datetime import date

from backend.db.queries.channels import (
    get_active_roster,
    get_channel,
    get_synthesis_cache,
    save_synthesis,
)
from backend.db.queries.messages import get_full_transcript, get_last_message_id
from backend.db.queries.profiles import get_moderador_profile
from backend.services.llm import stream_turn

_SYNTHESIS_PROMPT = """\
Sintetiza la siguiente tertulia. Sé fiel al debate real: captura el choque de posturas \
y el gestalt emergente, no un resumen plano.

Canal: {title}
Modo: {mode}
Participantes: {participants}
Fecha: {date}

TRANSCRIPCIÓN COMPLETA:
{transcript}

Genera exactamente la siguiente plantilla, sin añadir texto antes ni después:

---
title: {title}
date: {date}
type: tertulia-sintesis
mode: {mode}
participants: [{participants}]
tags: [tertulia]
---

# <Tema / pregunta de partida>

## El tema
<1–2 frases: qué se trajo a la tertulia>

## Posturas
{posture_lines}

## Puntos de fricción
<dónde chocaron de verdad las posturas — aquí está el jugo>

## El gestalt
<lo que nadie dijo entero pero emergió de la suma de todos>

## Qué nos llevamos
<conclusiones, decisiones, próximos pasos>

## Preguntas abiertas
- <lo que quedó sin resolver>
"""


async def run_synthesis(channel_id: int) -> AsyncGenerator[str, None]:
    channel = await get_channel(channel_id)
    if not channel:
        yield f"data: {json.dumps({'type': 'error', 'message': 'Canal no encontrado'})}\n\n"
        return

    moderador = await get_moderador_profile()
    if not moderador:
        yield f"data: {json.dumps({'type': 'error', 'message': 'Perfil Moderador no encontrado en la BD'})}\n\n"
        return

    rows = await get_full_transcript(channel_id)
    if not rows:
        yield f"data: {json.dumps({'type': 'error', 'message': 'El canal no tiene mensajes'})}\n\n"
        return

    last_msg_id = await get_last_message_id(channel_id)

    # Return cached synthesis if the conversation hasn't advanced since it was generated
    cached = await get_synthesis_cache(channel_id)
    if cached and cached["up_to_msg_id"] == last_msg_id:
        yield f"data: {json.dumps({'type': 'start'})}\n\n"
        yield f"data: {json.dumps({'type': 'token', 'token': cached['content']}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return

    roster = await get_active_roster(channel_id)
    participant_names = [p["name"] for p in roster] if roster else []

    transcript = "\n\n".join(
        f"{'Tú' if r['role'] == 'human' else r['speaker']}: {r['content']}"
        for r in rows
    )

    posture_lines = (
        "\n".join(
            f"- **{name}**: <su posición, 1–2 frases>" for name in participant_names
        )
        or "- <posición de cada participante, 1–2 frases>"
    )

    user_prompt = _SYNTHESIS_PROMPT.format(
        title=channel["title"] or "Sin título",
        mode=channel["mode"],
        participants=", ".join(participant_names)
        if participant_names
        else "desconocidos",
        date=date.today().strftime("%Y-%m-%d"),
        transcript=transcript,
        posture_lines=posture_lines,
    )

    yield f"data: {json.dumps({'type': 'start'})}\n\n"

    accumulated = []
    try:
        async for chunk in stream_turn(
            system=moderador["system_prompt"],
            messages=[{"role": "user", "content": user_prompt}],
            model=moderador["model"],
            temperature=moderador["temperature"],
        ):
            if isinstance(chunk, str):
                accumulated.append(chunk)
                yield f"data: {json.dumps({'type': 'token', 'token': chunk}, ensure_ascii=False)}\n\n"
    except Exception as exc:
        yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
        return

    if accumulated and last_msg_id is not None:
        await save_synthesis(channel_id, "".join(accumulated), last_msg_id)

    yield f"data: {json.dumps({'type': 'done'})}\n\n"
