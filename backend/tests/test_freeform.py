import json
from dataclasses import replace

import pytest

from conftest import CAMPAIGN_PATH
from devaneio.game import (
    CommandError,
    GameOverError,
    LlmUnavailableError,
    execute,
    format_output,
    is_command,
    new_game,
    run_freeform,
)
from devaneio.llm import LlmError
from fakes import ScriptedClient


def reply(*actions, say=""):
    return json.dumps({"actions": list(actions), "say": say})


CHECK = {"kind": "check", "skill": "furtividade", "difficulty": "normal"}
MOVE = {"kind": "move", "to": "floresta"}


@pytest.fixture
def base(tmp_path):
    session = new_game(CAMPAIGN_PATH, tmp_path / "p.json", seed=7)
    session, _ = execute(session, 'entrar aria "Aria" FOR=3 +espada')
    return session


def with_llm(session, *replies):
    client = ScriptedClient(*replies)
    return replace(session, llm=client), client


def kinds(session):
    return [e.kind for e in session.state.events]


# --- is_command ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("ir floresta", True),
        ("IR floresta", True),
        ("aria: ir floresta", True),
        ('entrar aria "Aria', True),  # aspas soltas não escondem o comando
        ("tento ir até a floresta", False),
        ("digo: olá, Bram", False),
        ("aria:", False),
        ("", False),
        ("   ", False),
    ],
)
def test_is_command(line, expected):
    assert is_command(line) is expected


# --- fluxo feliz ------------------------------------------------------------------


def test_proposal_runs_through_the_engine(base):
    session, client = with_llm(base, reply(CHECK, MOVE, say="Você some entre as sombras."))
    result = run_freeform(session, "tento passar sem ser vista e sigo para a floresta")
    assert result.commands == ("testar furtividade normal", "ir floresta")
    assert result.say == "Você some entre as sombras."
    assert kinds(result.session)[-3:] == [
        "check",
        "move",
        "beat_done",
    ]  # o diretor concluiu o marco
    assert result.session.state.current_location_id == "floresta"
    assert result.session.state.rng_draws == 2  # a rolagem é do motor, não do modelo
    call = client.calls[0]
    assert call["json_mode"] is True
    assert call["temperature"] == 0.2
    assert len(client.calls) == 1
    assert "APENAS com um objeto JSON" in call["messages"][0]["content"]
    assert call["messages"][1]["content"].endswith(
        "JOGADOR (Aria): tento passar sem ser vista e sigo para a floresta"
    )
    assert base.state.current_location_id == "vila"  # a sessão original não muda


def test_say_only_changes_nothing(base):
    session, _ = with_llm(base, reply(say="Bram resmunga e volta à bigorna."))
    result = run_freeform(session, "pergunto a Bram sobre o irmão dele")
    assert result.say == "Bram resmunga e volta à bigorna."
    assert result.commands == ()
    assert result.session.state == base.state


def test_markdown_fenced_reply_is_accepted(base):
    session, _ = with_llm(base, "```json\n" + reply(MOVE) + "\n```")
    assert run_freeform(session, "vou").session.state.current_location_id == "floresta"


# --- feedback e nova tentativa ---------------------------------------------------


def test_invalid_json_is_retried_with_feedback(base):
    session, client = with_llm(base, "não sei o que fazer", reply(MOVE))
    result = run_freeform(session, "vou")
    assert result.session.state.current_location_id == "floresta"
    assert len(client.calls) == 2
    retry = client.calls[1]["messages"]
    assert retry[-2] == {"role": "assistant", "content": "não sei o que fazer"}
    assert retry[-1]["role"] == "user"
    assert "recusada" in retry[-1]["content"]
    assert "não contém um objeto JSON" in retry[-1]["content"]


def test_engine_refusal_is_fed_back(base):
    bad = {"kind": "check", "skill": "voar", "difficulty": "normal"}
    session, client = with_llm(base, reply(bad), reply(CHECK))
    result = run_freeform(session, "tento voar")
    assert result.commands == ("testar furtividade normal",)
    feedback = client.calls[1]["messages"][-1]["content"]
    assert "ação 'testar voar normal' recusada" in feedback
    assert "habilidade 'voar'" in feedback


def test_two_failures_give_up_and_leave_the_session_untouched(base):
    session, client = with_llm(base, "lixo", reply({"kind": "move", "to": "lua"}))
    with pytest.raises(
        CommandError, match=r"o mestre \(LLM\) não propôs uma ação válida.*local 'lua'"
    ):
        run_freeform(session, "vou à lua")
    assert len(client.calls) == 2
    assert session.state == base.state


def test_all_or_nothing(base):
    # o movimento valeria sozinho, mas o arco não está no inventário: nada é aplicado
    broken = reply(MOVE, {"kind": "attack", "weapon": "arco", "target": "ferreiro"})
    session, client = with_llm(base, broken, reply(say="Melhor não."))
    result = run_freeform(session, "fujo e atiro")
    assert result.session.state.current_location_id == "vila"
    assert result.commands == ()
    assert "Aria não tem 'arco'" in client.calls[1]["messages"][-1]["content"]


def test_ids_cannot_inject_commands(base):
    evil = reply({"kind": "move", "to": "floresta; ferir aria 99"})
    session, client = with_llm(base, evil, reply(MOVE))
    result = run_freeform(session, "vou")
    assert "String should match pattern" in client.calls[1]["messages"][-1]["content"]
    assert result.session.state.characters["aria"].hp == 12  # nenhum ferir rodou


def test_too_many_actions_are_refused(base):
    session, client = with_llm(base, reply(*[{"kind": "rest"}] * 4), reply(say="calma"))
    result = run_freeform(session, "faço muita coisa")
    assert result.commands == ()
    assert "actions" in client.calls[1]["messages"][-1]["content"]


# --- ator, estado da partida, erros ------------------------------------------------


def test_actor_prefix_and_ambiguity(base):
    session, _ = execute(base, 'entrar zed "Zed" MEN=4')
    session, _ = with_llm(session, reply(CHECK))
    with pytest.raises(CommandError, match="há vários personagens \\(aria, zed\\)"):
        run_freeform(session, "tento passar")
    session, client = with_llm(session, reply(CHECK))
    result = run_freeform(session, "zed: tento passar")
    check = next(e for e in result.session.state.events if e.kind == "check")
    assert check.data["actor_id"] == "zed"
    assert client.calls[0]["messages"][1]["content"].endswith("JOGADOR (Zed): tento passar")


def test_colon_in_plain_text_is_not_an_actor_prefix(base):
    session, client = with_llm(base, reply(say="ok"))
    run_freeform(session, "digo: olá, Bram")
    assert client.calls[0]["messages"][1]["content"].endswith("JOGADOR (Aria): digo: olá, Bram")


def test_llm_error_becomes_a_command_error(base):
    session, _ = with_llm(base, LlmError("rede caiu"))
    with pytest.raises(CommandError, match="o LLM falhou: rede caiu"):
        run_freeform(session, "vou")


def test_refused_after_the_game_ended(base):
    session, _ = execute(base, "ferir aria 99")
    session, client = with_llm(session, reply(MOVE))
    with pytest.raises(GameOverError, match="a partida terminou") as info:
        run_freeform(session, "vou")
    assert info.value.status.value == "lost"
    assert client.calls == []


def test_requires_a_configured_llm(base):
    with pytest.raises(CommandError, match="não está configurado"):
        run_freeform(base, "vou")


# --- saída com LLM -----------------------------------------------------------------


def test_format_output_uses_llm_prose_with_mechanical_lines(base):
    after, text = execute(base, "ir floresta")
    client = ScriptedClient("A trilha se abre entre pinheiros altos.")
    out = format_output(base.narrator, base.state, after.state, text, client)
    lines = out.split("\n")
    assert lines[0] == "A trilha se abre entre pinheiros altos."
    assert lines[1:] == [
        "  [O grupo vai de Vila de Pedra Alta para Floresta Cinzenta.]",
        "  [Marco concluído: Chegada à vila.]",
    ]
    assert len(client.calls) == 1  # um parágrafo por ação, não por evento


def test_format_output_falls_back_to_the_grammar_with_a_note(base):
    after, text = execute(base, "ir floresta")
    out = format_output(
        base.narrator, base.state, after.state, text, ScriptedClient(LlmError("fora do ar"))
    )
    assert "(narração por LLM indisponível: fora do ar; usei a gramática)" in out
    assert "Floresta Cinzenta" in out.split("\n")[0]
    assert "  [Marco concluído: Chegada à vila.]" in out


# --- ator fixo e allow --------------------------------------------------------------


def test_a_fixed_actor_wins_over_a_prefix_in_the_text(base):
    session, _ = execute(base, 'entrar zed "Zed"')
    session, client = with_llm(session, reply(CHECK))
    result = run_freeform(session, "aria: tento passar", actor="zed")
    check = next(e for e in result.session.state.events if e.kind == "check")
    assert check.data["actor_id"] == "zed"
    assert client.calls[0]["messages"][1]["content"].endswith("JOGADOR (Zed): aria: tento passar")


def test_allow_sees_each_line_with_the_session_already_advanced(base):
    seen = []

    def allow(working, line):
        seen.append((working.state.current_location_id, line))

    session, _ = with_llm(base, reply(MOVE, CHECK))
    run_freeform(session, "vou e tento passar", allow=allow)
    assert seen == [
        ("vila", "aria: ir floresta"),
        ("floresta", "aria: testar furtividade normal"),
    ]


def test_a_refusal_from_allow_goes_back_to_the_model_as_feedback(base):
    def allow(_working, line):
        if "ir " in line:
            raise CommandError("não pode ir")

    session, client = with_llm(base, reply(MOVE), reply(CHECK))
    result = run_freeform(session, "vou", allow=allow)
    assert result.commands == ("testar furtividade normal",)
    assert "ação 'ir floresta' recusada: não pode ir" in client.calls[1]["messages"][-1]["content"]
    assert session.state == base.state  # a entrada não mudou


def test_allow_refusing_every_attempt_leaves_the_state_alone(base):
    def allow(_working, _line):
        raise CommandError("nada passa")

    session, _ = with_llm(base, reply(MOVE), reply(MOVE))
    with pytest.raises(CommandError, match="nada passa"):
        run_freeform(session, "vou", allow=allow)


def test_an_llm_outage_is_its_own_error_and_still_a_command_error(base):
    session, _ = with_llm(base, LlmError("rede caiu"))
    with pytest.raises(LlmUnavailableError, match="o LLM falhou: rede caiu") as info:
        run_freeform(session, "vou")
    assert isinstance(info.value, CommandError)


def test_hidden_events_are_not_sent_to_the_model(base):
    session, _ = execute(base, 'ferir sacerdote 2 "armadilha"')
    session, client = with_llm(session, reply(say="ok"))
    last = len(session.state.events) - 1
    run_freeform(session, "olho em volta", hide_events=frozenset({last}))
    assert "Irmão Vael" not in client.calls[0]["messages"][1]["content"]
    session, client = with_llm(session, reply(say="ok"))
    run_freeform(session, "olho em volta")
    assert "Irmão Vael" in client.calls[0]["messages"][1]["content"]  # sem ocultar, vai


def test_secrets_are_sent_unless_the_caller_leaves_them_out(base):
    session, _ = execute(base, "ir floresta")
    session, _ = execute(session, "ir ruinas")
    session, client = with_llm(session, reply(say="ok"), reply(say="ok"))
    run_freeform(session, "olho em volta")
    assert "líder do culto" in client.calls[0]["messages"][1]["content"]
    run_freeform(session, "olho em volta", include_private=False)
    assert "líder do culto" not in client.calls[1]["messages"][1]["content"]
