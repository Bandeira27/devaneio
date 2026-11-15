import json

import pytest

from devaneio.engine import add_character, apply_damage, initial_state, reveal_fact
from devaneio.llm import (
    CopilotContextTooLarge,
    LlmError,
    ask_copilot,
    build_context,
    build_copilot_context,
    build_copilot_messages,
    copilot,
)
from devaneio.llm.copilot import (
    COPILOT_SYSTEM,
    MAX_ANSWER_CHARS,
    RECENT_EVENTS,
    TEXT_CUT,
    fit_context,
)
from devaneio.llm.text import clean_multiline
from devaneio.schema import Event
from fakes import ScriptedClient


@pytest.fixture
def state(campaign, rules):
    s = initial_state(campaign, rules, 3)
    return add_character(s, rules, character_id="aria", name="Aria").state


def ctx(campaign, rules, state):
    return build_copilot_context(campaign, rules, state)


def test_the_context_has_the_whole_campaign_including_what_is_private(campaign, rules, state):
    data = campaign.model_dump()
    data["locations"][0]["private_notes"] = ["a vila esconde um poço"]
    data["beats"][2]["private_notes"] = ["Vael foge se ferido"]
    campaign = type(campaign).model_validate(data)
    context = ctx(campaign, rules, state)

    assert [loc["id"] for loc in context["locais"]] == [loc.id for loc in campaign.locations]
    assert context["locais"][0]["notas_privadas"] == ["a vila esconde um poço"]
    assert [f["id"] for f in context["faccoes"]] == [f.id for f in campaign.factions]
    assert {n["id"] for n in context["npcs"]} == {
        n.id for n in campaign.npcs
    }  # os de outros locais também
    beats = {b["id"]: b for b in context["marcos"]}
    assert set(beats) == {b.id for b in campaign.beats}
    assert beats["confronto"]["estado"] == "pending"
    assert beats["confronto"]["notas_privadas"] == ["Vael foge se ferido"]
    assert {"kind": "npc_down", "npc_id": "sacerdote"} in beats["confronto"]["conclui_quando"]
    hidden = next(f for f in context["fatos"] if f["id"] == "sacerdote-segredo")
    assert hidden["revelado"] is False
    assert hidden["texto"] == "Irmão Vael é o líder do culto."
    assert hidden["sobre"] == "Irmão Vael"
    assert {"kind": "npc_down", "npc_id": "sacerdote"} in hidden["revela_quando"]


def test_revealed_facts_say_when_and_the_random_state_never_goes(campaign, rules, state):
    revealed = reveal_fact(state, campaign, fact_id="ferreiro-segredo").state
    context = ctx(campaign, rules, revealed)
    fact = next(f for f in context["fatos"] if f["id"] == "ferreiro-segredo")
    assert fact["revelado"] is True
    assert fact["revelado_no_turno"] == revealed.turn
    dumped = json.dumps(context)
    assert "rng_seed" not in dumped
    assert "rng_draws" not in dumped


def test_npc_state_is_in_the_context(campaign, rules, state):
    hurt = apply_damage(
        state, campaign, target_kind="npc", target_id="sacerdote", amount=99, source="x"
    ).state
    npc = next(n for n in ctx(campaign, rules, hurt)["npcs"] if n["id"] == "sacerdote")
    assert npc["de_pe"] is False
    assert npc["local"] == "ruinas"
    assert npc["hostil"] is True


def test_only_the_last_events_go_and_none_is_filtered(campaign, rules, state):
    state.events.extend(Event(turn=0, kind="x", text=f"evento {i}") for i in range(30))
    events = ctx(campaign, rules, state)["eventos_recentes"]
    assert events == [f"evento {i}" for i in range(30 - RECENT_EVENTS, 30)]


def test_the_players_context_still_leaves_out_what_the_copilot_sees(campaign, rules, state):
    """O recorte público do /say não muda: marco pendente, facção e fato oculto de NPC ausente ficam de fora."""
    public = json.dumps(build_context(campaign, rules, state, "aria", include_private=False))
    private = json.dumps(ctx(campaign, rules, state), ensure_ascii=False)
    assert "Culto da Sombra" not in public
    assert "Culto da Sombra" in private
    assert "líder do culto" not in public
    assert "líder do culto" in private


def test_the_messages_carry_the_system_prompt_context_and_question(campaign, rules, state):
    system, user = build_copilot_messages(campaign, rules, state, "O que faço agora?")
    assert system == {"role": "system", "content": COPILOT_SYSTEM}
    assert user["role"] == "user"
    assert "PERGUNTA DO ANFITRIÃO\nO que faço agora?" in user["content"]
    assert "líder do culto" in user["content"]
    assert "NÃO altera o jogo" in COPILOT_SYSTEM


def test_ask_makes_one_plain_text_call_and_returns_the_clean_answer(campaign, rules, state):
    client = ScriptedClient("Sugestão:\n\n- vá à floresta\x1b[31m\n")
    answer = ask_copilot(client, campaign, rules, state, "e agora?")
    assert answer == "Sugestão:\n\n- vá à floresta[31m"
    (call,) = client.calls
    assert call["json_mode"] is False
    assert call["temperature"] == 0.5


def test_an_empty_answer_is_an_llm_error(campaign, rules, state):
    with pytest.raises(LlmError, match="vazia"):
        ask_copilot(ScriptedClient(" \x1b \n"), campaign, rules, state, "oi")


def test_a_failing_client_error_goes_up_as_is(campaign, rules, state):
    with pytest.raises(LlmError, match="caiu"):
        ask_copilot(ScriptedClient(LlmError("caiu")), campaign, rules, state, "oi")


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ("a\nb", "a\nb"),
        ("a\r\nb\rc", "a\nb\nc"),
        ("a\t\tb   c", "a b c"),
        ("a\n\n\n\nb", "a\n\nb"),
        ("\n\n  a  \n\n", "a"),
        ("a\u202eb\u200bc\x07d", "abcd"),
        ("a\u2028b", "a b"),  # separador de linha unicode vira espaço, como em clean_text
    ],
)
def test_clean_multiline_keeps_line_breaks_and_drops_what_deceives(raw, clean):
    assert clean_multiline(raw, 100) == clean


def test_clean_multiline_cuts_at_the_limit():
    assert clean_multiline("x" * 5000, MAX_ANSWER_CHARS) == "x" * MAX_ANSWER_CHARS


def test_an_npc_without_state_is_unknown_not_fallen(campaign, rules, state):
    del state.npcs["ferreiro"]
    npc = next(n for n in ctx(campaign, rules, state)["npcs"] if n["id"] == "ferreiro")
    assert npc["de_pe"] is None
    assert npc["hp"] is None
    assert npc["hostil"] is None
    assert npc["local"] == "vila"


def test_a_campaign_without_factions_beats_or_facts_gives_empty_lists(campaign, rules):
    data = campaign.model_dump()
    data["factions"] = []
    data["beats"] = []
    data["facts"] = []
    bare = type(campaign).model_validate(data)
    state = initial_state(bare, rules, 3)
    context = ctx(bare, rules, state)
    assert context["faccoes"] == []
    assert context["marcos"] == []
    assert context["fatos"] == []
    assert build_copilot_messages(bare, rules, state, "oi")[1]["content"]


def test_a_fact_about_nothing_has_no_subject(campaign, rules, state):
    data = campaign.model_dump()
    data["facts"][0]["about"] = None
    free = type(campaign).model_validate(data)
    fact = ctx(free, rules, state)["fatos"][0]
    assert fact["sobre"] is None


def test_an_npc_marked_dead_is_not_standing_even_with_hp(campaign, rules, state):
    state.npcs["ferreiro"] = state.npcs["ferreiro"].model_copy(update={"alive": False})
    npc = next(n for n in ctx(campaign, rules, state)["npcs"] if n["id"] == "ferreiro")
    assert npc["de_pe"] is False


def test_an_answer_of_only_blanks_is_an_llm_error(campaign, rules, state):
    with pytest.raises(LlmError, match="vazia"):
        ask_copilot(ScriptedClient("   \n\t \n  "), campaign, rules, state, "oi")


# --- teto de tamanho -------------------------------------------------------------------


def with_events(state, count, size):
    state.events.extend(Event(turn=0, kind="x", text=f"e{i}" + "y" * size) for i in range(count))
    return state


def test_a_normal_campaign_is_not_reduced(campaign, rules, state):
    context, text = fit_context(ctx(campaign, rules, with_events(state, 15, 50)))
    assert "aviso" not in context
    assert len(context["eventos_recentes"]) == 15
    assert len(text) < 20_000


def test_over_the_cap_the_oldest_events_go_first_and_the_model_is_told(
    campaign, rules, state, monkeypatch
):
    state = with_events(state, 15, 2000)  # ~30 mil caracteres só de eventos
    base = ctx(campaign, rules, state)
    without_events = len(copilot._dump({**base, "eventos_recentes": []}))
    monkeypatch.setattr(copilot, "MAX_CONTEXT_CHARS", without_events + 12_000)
    context, _ = fit_context(base)
    assert len(context["eventos_recentes"]) == copilot.REDUCED_EVENTS
    assert context["eventos_recentes"][-1] == base["eventos_recentes"][-1]  # os mais novos ficam
    assert "só os 5 eventos mais recentes" in context["aviso"]

    monkeypatch.setattr(copilot, "MAX_CONTEXT_CHARS", without_events + 500)
    context, _ = fit_context(base)
    assert context["eventos_recentes"] == []
    assert "sem eventos recentes" in context["aviso"]


def test_then_long_texts_are_cut_and_ids_stay(campaign, rules, state, monkeypatch):
    data = campaign.model_dump()
    data["locations"][0]["description"] = "z" * 5000
    big = type(campaign).model_validate(data)
    base = ctx(big, rules, state)
    monkeypatch.setattr(copilot, "MAX_CONTEXT_CHARS", len(copilot._dump(base)) - 1000)
    context, _ = fit_context(base)
    assert len(context["locais"][0]["descricao"]) == TEXT_CUT
    assert context["locais"][0]["descricao"].endswith("…")
    assert context["locais"][0]["id"] == base["locais"][0]["id"]
    assert "textos longos cortados" in context["aviso"]


def test_an_absurd_campaign_is_refused_with_a_clear_error(campaign, rules, state, monkeypatch):
    monkeypatch.setattr(copilot, "MAX_CONTEXT_CHARS", 500)
    with pytest.raises(CopilotContextTooLarge, match="teto do copiloto é 500"):
        ask_copilot(ScriptedClient("x"), campaign, rules, state, "oi")


def test_the_messages_carry_the_reduction_notice(campaign, rules, state, monkeypatch):
    state = with_events(state, 15, 2000)
    base = ctx(campaign, rules, state)
    monkeypatch.setattr(
        copilot, "MAX_CONTEXT_CHARS", len(copilot._dump({**base, "eventos_recentes": []})) + 500
    )
    _, user = build_copilot_messages(campaign, rules, state, "oi")
    assert "Contexto reduzido por tamanho" in user["content"]
