from anthropic import AsyncAnthropic

from backend.config import settings
from backend.db.queries.messages import (
    count_messages_after,
    get_latest_summary,
    get_messages_chunk,
    insert_summary,
)
from backend.logger import logger

COMPRESSION_THRESHOLD = 30
COMPRESSION_CHUNK = 20
ACTA_MAX_TOKENS = 800
_ACTA_GEN_TOKENS = 1200  # headroom over ACTA_MAX_TOKENS for generation
_HAIKU = "claude-haiku-4-5-20251001"

_client = AsyncAnthropic(api_key=settings.anthropic_api_key)

_SYSTEM = (
    "Eres el actualizador del acta de una tertulia. "
    "Tu tarea es devolver el acta completa y actualizada en markdown. "
    "Solo el acta, sin preámbulos ni comentarios fuera del acta."
)

_INSTRUCTIONS = """\
Actualiza el siguiente acta de tertulia incorporando los mensajes nuevos.

INSTRUCCIONES:
- Conserva TODAS las entradas del acta anterior salvo que los mensajes nuevos \
las modifiquen, las resuelvan o las vuelvan irrelevantes.
- Devuelve el acta completa actualizada (no un delta, no un resumen del chunk).
- Toda posición, concesión u observación debe llevar nombre de hablante.
- El acta no debe superar aproximadamente {max_tokens} tokens. Si hay que condensar, \
hazlo primero en "Temas cerrados" y "Datos y referencias clave". \
Nunca recortes "Posiciones por hablante" ni "Desacuerdos abiertos".
- Redacta el acta en español.
"""

_FORMAT_DEBATE = """\
Formato del acta (modo debate):

## Tema y arranque
(1-2 frases: de qué va la tertulia y cómo se planteó)

## Posiciones por hablante
- **Nombre:** (postura actual, 1-3 frases)

## Desacuerdos abiertos
- (punto de fricción no resuelto, quién está en cada lado)

## Concesiones y giros
- (quién cambió de postura o cedió en qué)

## Temas cerrados
- (acuerdos alcanzados o líneas abandonadas)

## Datos y referencias clave
- (hechos, ejemplos, citas o referencias que podrían reaparecer)
"""

_FORMAT_CRITICA = """\
Formato del acta (modo critica):

## Texto y objetivo
(qué texto se está criticando y qué pidió el autor)

## Observaciones por crítico
- **Nombre:** (sus señalamientos principales vigentes)

## Sugerencias sobre la mesa
- (propuestas de cambio concretas aún no resueltas)

## Decisiones del autor
- (qué ha aceptado, rechazado o aplazado)

## Fragmentos clave citados
- (pasajes del texto que se han discutido, identificados brevemente)
"""


def _build_user_message(
    previous_acta: str | None,
    chunk: list[dict],
    mode: str,
) -> str:
    lines = [
        f"{m['profile_name'] or m['role']}: {m['content']}"
        for m in chunk
        if m["role"] != "system"
    ]
    mensajes_nuevos = "\n".join(lines)

    fmt = _FORMAT_CRITICA if mode == "critica" else _FORMAT_DEBATE
    instructions = _INSTRUCTIONS.format(max_tokens=ACTA_MAX_TOKENS)

    if previous_acta:
        acta_block = f"<acta_anterior>\n{previous_acta}\n</acta_anterior>"
    else:
        acta_block = "<acta_anterior>\nNo hay acta anterior. Genera el acta desde cero.</acta_anterior>"

    return (
        f"{instructions}\n"
        f"{acta_block}\n\n"
        f"<mensajes_nuevos>\n{mensajes_nuevos}\n</mensajes_nuevos>\n\n"
        f"{fmt}"
    )


async def _update_acta(
    previous_acta: str | None,
    chunk: list[dict],
    mode: str,
) -> str:
    user_msg = _build_user_message(previous_acta, chunk, mode)
    response = await _client.messages.create(
        model=_HAIKU,
        max_tokens=_ACTA_GEN_TOKENS,
        temperature=0.2,
        system=_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    return response.content[0].text


async def maybe_compress(channel_id: int, mode: str = "debate") -> None:
    summary = await get_latest_summary(channel_id)
    after_id = summary["covers_up_to_msg_id"] if summary else None
    count = await count_messages_after(channel_id, after_id)
    if count < COMPRESSION_THRESHOLD:
        return

    chunk = await get_messages_chunk(channel_id, after_id, limit=COMPRESSION_CHUNK)
    if not chunk:
        return

    previous_acta: str | None = summary["content"] if summary else None

    try:
        new_acta = await _update_acta(previous_acta, chunk, mode)
    except Exception as exc:
        logger.error(
            "compressor: fallo al actualizar acta channel_id={} — turno continúa sin comprimir: {}",
            channel_id,
            exc,
        )
        return

    if not new_acta or not new_acta.strip():
        logger.warning(
            "compressor: acta vacía devuelta por Haiku channel_id={} — descartada",
            channel_id,
        )
        return

    last_id = chunk[-1]["id"]
    await insert_summary(channel_id, new_acta, covers_up_to_msg_id=last_id)

    logger.info(
        "compressor: acta actualizada channel_id={} covers_up_to={} "
        "acta_anterior_chars={} acta_nueva_chars={}",
        channel_id,
        last_id,
        len(previous_acta) if previous_acta else 0,
        len(new_acta),
    )
    logger.debug("compressor: acta resultante channel_id={}:\n{}", channel_id, new_acta)
