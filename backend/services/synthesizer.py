import json
from collections.abc import AsyncGenerator
from datetime import date

from backend.db.queries.channels import get_active_roster, get_channel
from backend.db.queries.messages import get_full_transcript
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

    try:
        async for chunk in stream_turn(
            system=moderador["system_prompt"],
            messages=[{"role": "user", "content": user_prompt}],
            model=moderador["model"],
            temperature=moderador["temperature"],
        ):
            if isinstance(chunk, str):
                yield f"data: {json.dumps({'type': 'token', 'token': chunk}, ensure_ascii=False)}\n\n"
            # usage stats not saved for utility calls
    except Exception as exc:
        yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
        return

    yield f"data: {json.dumps({'type': 'done'})}\n\n"
