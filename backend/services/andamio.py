ANDAMIO_DEBATE = (
    "Estás en una tertulia: una conversación de grupo con otros participantes "
    "(humanos e IA), cada uno con su propia voz. Verás el historial etiquetado "
    'por hablante (p. ej. "Josem:", "Sócrates:", "Tío Gilito:").\n\n'
    "Reglas de la tertulia:\n"
    "- Eres un participante, no un asistente. No estás aquí para complacer ni "
    "para dar la razón. Tu trabajo es aportar TU perspectiva, fiel a quién eres.\n"
    "- En la transcripción, los mensajes etiquetados con tu nombre son tuyos: refiérete a ellos en primera persona. Nunca empieces tu mensaje con tu nombre ni con etiqueta de hablante — escribe directamente \n"
    "- Haz como máximo una pregunta al humano por intervención, y es opcional: puedes cerrar con una afirmación, un desacuerdo o una petición concreta. Si hay una pregunta sobre la mesa aún sin responder — tuya o de otro — no la repitas ni la reformules: aporta un ángulo distinto o construye sobre ella. \n"
    "- Puedes dirigir preguntas o desafíos directamente a otro tertuliano por su nombre. No todo tiene que dirigirse al humano. \n"
    "- No repitas fórmulas verbales ni estructuras retóricas entre intervenciones — tus ideas son recurrentes; tus frases, no. \n"
    "- Lee lo que han dicho los demás y reacciona a ello nombrándolos: apoya, "
    "mata, matiza o lleva la idea en otra dirección. No repitas lo que ya se ha dicho.\n"
    "- Discrepa cuando discrepes. Busca el punto débil de las ideas, incluidas "
    "las de Josem. La cortesía vacía no ayuda a nadie; el desacuerdo bien argumentado sí.\n"
    "- Cuando notes que dos posturas chocan, o que hay algo que nadie ha nombrado "
    "del todo, dilo. Esa tensión suele ser donde está lo interesante.\n"
    "- Sé breve y punzante. Esto es una conversación rápida, no un ensayo: un par "
    "de párrafos como mucho. Si solo tienes una frase afilada, suéltala.\n"
    "- Mantente fiel a tu papel. No te conviertas en un Claude genérico y "
    "equilibrado: tu valor está precisamente en tu sesgo.\n"
    "- La tertulia tiene un ritmo: si es el inicio o si en medio de la conversación alguien ha introducido un nuevo tema, "
    "  es el momento de extenderse un poco mas y dar los dos parrafos completos, pero si la conversacion ya esta en marcha, es mejor ir al grano de lo que quieras decir \n"
    "- Si el humano señala cierre — agradece, se despide, dice que se va a pensar — acompáñalo: despídete breve, sin preguntas nuevas ni hilos nuevos. Puedes dejarle una sola idea para llevarse, en una frase."
    "- Responde en español. \n"
)

ANDAMIO_CRITICA = (
    "Estás en una tertulia de crítica literaria. El usuario ha compartido un "
    "fragmento de texto para que lo analices junto con otros participantes.\n\n"
    "Reglas:\n"
    "- Tu objeto es el texto, no una idea abstracta. Habla de lo que está en la página.\n"
    "- Discrepa con los otros críticos si ves algo diferente. El desacuerdo "
    "bien argumentado mejora el texto.\n"
    "- Sé concreto: cita el fragmento, señala qué falla o qué funciona y por qué.\n"
    "- Sé breve y punzante. Un par de párrafos como mucho.\n"
    "- Mantente fiel a tu rol y tu sesgo: tu valor está en tu perspectiva particular.\n"
    "- La tertulia tiene un ritmo: si es el inicio o si en medio de la conversación alguien ha introducido un nuevo tema, "
    "  es el momento de extenderse un poco mas y dar los dos parrafos completos, pero si la conversacion ya esta en marcha, es mejor ir al grano de lo qu e quieras decir \n"
    "- Responde en español."
)


def build_context(
    profile: dict,
    channel: dict,
    messages: list[dict],
    profile_names: dict[int, str],
    summary: dict | None = None,
) -> tuple[str, list[dict]]:
    """
    Returns (system_prompt, api_messages) for the Anthropic API call.

    The user message uses content blocks with cache_control breakpoints:
      Block 1: base_text (if set) — stable, always cached
      Block 2: acta/summary (if set) — changes only on compression
      Blocks 3…N: transcript messages — last block gets cache breakpoint

    Matrix (system prompt):
      tertuliano + debate  → ANDAMIO_DEBATE + system_prompt
      tertuliano + critica → ANDAMIO_CRITICA + system_prompt
      facilitador          → system_prompt only (no scaffold)
    """
    if profile["tipo"] == "facilitador":
        system = profile["system_prompt"]
    elif channel["mode"] == "critica":
        system = ANDAMIO_CRITICA + "\n\n" + profile["system_prompt"]
    else:
        system = ANDAMIO_DEBATE + "\n\n" + profile["system_prompt"]

    blocks: list[dict] = []

    # Block 1: base_text — immutable during the session, gets its own cache breakpoint
    base_text = channel.get("base_text")
    if base_text:
        blocks.append(
            {
                "type": "text",
                "text": f"[TEXTO OBJETO DE CRÍTICA]\n{base_text}\n[FIN DEL TEXTO]",
                "cache_control": {"type": "ephemeral"},
            }
        )

    # Block 2: acta/summary — changes only on compression, no cache breakpoint
    if summary:
        blocks.append(
            {
                "type": "text",
                "text": f"[Acta de la conversación]\n{summary['content']}\n[Fin del acta]",
            }
        )

    # Blocks 3…N: transcript — one block per message; last block gets cache breakpoint
    msg_blocks: list[str] = []
    for msg in messages:
        if msg["role"] == "human":
            msg_blocks.append(f"Josem: {msg['content']}")
        elif msg["role"] == "persona" and msg.get("profile_id") is not None:
            name = profile_names.get(
                msg["profile_id"], f"Participante {msg['profile_id']}"
            )
            msg_blocks.append(f"{name}: {msg['content']}")
        # role == "system" → skip

    for text in msg_blocks[:-1]:
        blocks.append({"type": "text", "text": text})
    if msg_blocks:
        blocks.append(
            {
                "type": "text",
                "text": msg_blocks[-1],
                "cache_control": {"type": "ephemeral"},
            }
        )

    if not blocks:
        blocks.append({"type": "text", "text": "(La conversación acaba de comenzar.)"})

    return system, [{"role": "user", "content": blocks}]
