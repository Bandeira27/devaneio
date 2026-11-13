import json

import pytest

from devaneio.engine import add_character, initial_state, move
from devaneio.llm import MAX_ACTIONS, build_context, build_messages, feedback_message
from devaneio.llm.prompts import PROPOSER_SYSTEM


@pytest.fixture
def state(campaign, rules):
    s = initial_state(campaign, rules, 3)
    s = add_character(s, rules, character_id="aria", name="Aria", inventory=["espada", "tocha"]).state
    return add_character(s, rules, character_id="zed", name="Zed").state


def test_context_at_the_village(campaign, rules, state):
    ctx = build_context(campaign, rules, state, "aria")
    assert ctx["local"]["id"] == "vila"
    assert ctx["local"]["saidas"] == [{"id": "floresta", "nome": "Floresta Cinzenta"}]
    assert [n["id"] for n in ctx["npcs_aqui"]] == ["ferreiro"]  # sacerdote está nas ruínas
    assert ctx["npcs_aqui"][0]["hostil"] is False and ctx["npcs_aqui"][0]["de_pe"] is True
    assert ctx["personagem"]["id"] == "aria" and [g["id"] for g in ctx["grupo"]] == ["zed"]
    assert ctx["catalogo"]["armas_do_personagem"] == ["espada", "punhos"]  # tocha não é arma
    assert ctx["catalogo"]["alvos"] == ["zed", "ferreiro"]
    assert ctx["catalogo"]["saidas"] == ["floresta"]
    assert {s["id"] for s in ctx["catalogo"]["habilidades"]} >= {"lutar", "furtividade"}
    assert {d["id"] for d in ctx["catalogo"]["dificuldades"]} == {"facil", "normal", "dificil", "heroica"}
    assert [m["titulo"] for m in ctx["marcos_ativos"]] == []  # nada ativado ainda


def test_context_at_the_ruins_shows_hostile_priest_and_secrets(campaign, rules, state):
    s = move(move(state, campaign, to_location_id="floresta").state, campaign, to_location_id="ruinas").state
    ctx = build_context(campaign, rules, s, "zed")
    priest = ctx["npcs_aqui"][0]
    assert priest["id"] == "sacerdote" and priest["hostil"] is True
    assert priest["segredos"] == ["é o líder do culto"]
    assert ctx["catalogo"]["armas_do_personagem"] == ["punhos"]
    assert ctx["eventos_recentes"][-1].startswith("O grupo vai de Floresta Cinzenta")


def test_messages_shape(campaign, rules, state):
    messages = build_messages(campaign, rules, state, "aria", "tento passar sem ser visto")
    assert [m["role"] for m in messages] == ["system", "user"]
    assert messages[0]["content"] == PROPOSER_SYSTEM and "APENAS com um objeto JSON" in PROPOSER_SYSTEM
    assert f"No máximo {MAX_ACTIONS} ações" in PROPOSER_SYSTEM
    user = messages[1]["content"]
    assert user.startswith("CONTEXTO\n{") and user.endswith("JOGADOR (Aria): tento passar sem ser visto")
    json.loads(user.split("\n")[1])  # o contexto é JSON válido


def test_feedback_lists_every_problem():
    msg = feedback_message(["a", "b"])
    assert msg["role"] == "user" and "- a\n- b" in msg["content"]
