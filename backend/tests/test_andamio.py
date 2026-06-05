import pytest
from backend.services.andamio import build_context


def _profile(tipo: str = "tertuliano", system_prompt: str = "Eres Sócrates.") -> dict:
    return {
        "id": 1,
        "name": "Sócrates",
        "tipo": tipo,
        "system_prompt": system_prompt,
    }


def _channel(mode: str = "debate") -> dict:
    return {"id": 1, "mode": mode}


def test_tertuliano_debate_includes_andamio():
    system, msgs = build_context(_profile(), _channel("debate"), [], {})
    assert "tertulia" in system
    assert "Eres Sócrates." in system
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"


def test_facilitador_no_andamio():
    system, msgs = build_context(
        _profile("facilitador", "Eres RUIZ."), _channel(), [], {}
    )
    assert system == "Eres RUIZ."
    assert "tertulia" not in system


def test_tertuliano_critica_includes_andamio_critica():
    system, _ = build_context(_profile(), _channel("critica"), [], {})
    assert "texto" in system.lower() or "crítica" in system.lower()
    assert "Eres Sócrates." in system


def test_transcript_labels_human_as_josem():
    messages = [{"role": "human", "profile_id": None, "content": "¿SaaS?"}]
    _, msgs = build_context(_profile(), _channel(), messages, {})
    assert "Josem: ¿SaaS?" in msgs[0]["content"]


def test_transcript_labels_persona_by_name():
    messages = [{"role": "persona", "profile_id": 1, "content": "Buena pregunta"}]
    _, msgs = build_context(_profile(), _channel(), messages, {1: "Sócrates"})
    assert "Sócrates: Buena pregunta" in msgs[0]["content"]


def test_transcript_skips_system_role():
    messages = [
        {"role": "system", "profile_id": None, "content": "Ignorar"},
        {"role": "human", "profile_id": None, "content": "Hola"},
    ]
    _, msgs = build_context(_profile(), _channel(), messages, {})
    assert "Ignorar" not in msgs[0]["content"]
    assert "Josem: Hola" in msgs[0]["content"]


def test_summary_prepended_to_transcript():
    summary = {"content": "Resumen anterior aquí."}
    messages = [{"role": "human", "profile_id": None, "content": "¿Y ahora?"}]
    _, msgs = build_context(_profile(), _channel(), messages, {}, summary=summary)
    content = msgs[0]["content"]
    assert content.index("Resumen anterior aquí.") < content.index("Josem:")


def test_empty_messages_returns_empty_transcript():
    _, msgs = build_context(_profile(), _channel(), [], {})
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == ""
