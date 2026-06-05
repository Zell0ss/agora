ANDAMIO_DEBATE = (
    "Estás en una tertulia: una conversación de grupo con otros participantes "
    "(humanos e IA), cada uno con su propia voz. Verás el historial etiquetado "
    'por hablante (p. ej. "Josem:", "Sócrates:", "Tío Gilito:").\n\n'
    "Reglas de la tertulia:\n"
    "- Eres un participante, no un asistente. No estás aquí para complacer ni "
    "para dar la razón. Tu trabajo es aportar TU perspectiva, fiel a quién eres.\n"
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
    "- Responde en español."
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

    Matrix (from agora-disenio-decisiones.md §6):
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

    lines: list[str] = []

    if summary:
        lines.append(
            f"[Resumen de la conversación anterior]\n{summary['content']}\n[Fin del resumen]"
        )

    for msg in messages:
        if msg["role"] == "human":
            lines.append(f"Josem: {msg['content']}")
        elif msg["role"] == "persona" and msg.get("profile_id") is not None:
            name = profile_names.get(
                msg["profile_id"], f"Participante {msg['profile_id']}"
            )
            lines.append(f"{name}: {msg['content']}")
        # role == "system" → skip

    transcript = "\n".join(lines)
    return system, [{"role": "user", "content": transcript}]
