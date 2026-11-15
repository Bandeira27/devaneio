import json

import pytest

from devaneio.engine import add_character, initial_state, move, reveal_fact
from devaneio.llm import MAX_ACTIONS, build_context, build_messages, feedback_message
from devaneio.llm.prompts import PROPOSER_SYSTEM
from devaneio.schema import Event, FactDef


@pytest.fixture
def state(campaign, rules):
    s = initial_state(campaign, rules, 3)
    s = add_character(
        s, rules, character_id="aria", name="Aria", inventory=["espada", "tocha"]
    ).state
    return add_character(s, rules, character_id="zed", name="Zed").state


def test_context_at_the_village(campaign, rules, state):
    ctx = build_context(campaign, rules, state, "aria")
    assert ctx["local"]["id"] == "vila"
    assert ctx["local"]["saidas"] == [{"id": "floresta", "nome": "Floresta Cinzenta"}]
    assert [n["id"] for n in ctx["npcs_aqui"]] == ["ferreiro"]  # sacerdote está nas ruínas
    assert ctx["npcs_aqui"][0]["hostil"] is False
    assert ctx["npcs_aqui"][0]["de_pe"] is True
    assert ctx["personagem"]["id"] == "aria"
    assert [g["id"] for g in ctx["grupo"]] == ["zed"]
    assert ctx["catalogo"]["armas_do_personagem"] == ["espada", "punhos"]  # tocha não é arma
    assert ctx["catalogo"]["alvos"] == ["zed", "ferreiro"]
    assert ctx["catalogo"]["saidas"] == ["floresta"]
    assert {s["id"] for s in ctx["catalogo"]["habilidades"]} >= {"lutar", "furtividade"}
    assert {d["id"] for d in ctx["catalogo"]["dificuldades"]} == {
        "facil",
        "normal",
        "dificil",
        "heroica",
    }
    assert [m["titulo"] for m in ctx["marcos_ativos"]] == []  # nada ativado ainda


def test_context_at_the_ruins_shows_hostile_priest_and_secrets(campaign, rules, state):
    s = move(
        move(state, campaign, to_location_id="floresta").state, campaign, to_location_id="ruinas"
    ).state
    ctx = build_context(campaign, rules, s, "zed")
    priest = ctx["npcs_aqui"][0]
    assert priest["id"] == "sacerdote"
    assert priest["hostil"] is True
    assert priest["segredos"] == ["Irmão Vael é o líder do culto."]
    assert ctx["catalogo"]["armas_do_personagem"] == ["punhos"]
    assert ctx["eventos_recentes"][-1].startswith("O grupo vai de Floresta Cinzenta")


def test_messages_shape(campaign, rules, state):
    messages = build_messages(campaign, rules, state, "aria", "tento passar sem ser visto")
    assert [m["role"] for m in messages] == ["system", "user"]
    assert messages[0]["content"] == PROPOSER_SYSTEM
    assert "APENAS com um objeto JSON" in PROPOSER_SYSTEM
    assert f"No máximo {MAX_ACTIONS} ações" in PROPOSER_SYSTEM
    user = messages[1]["content"]
    assert user.startswith("CONTEXTO\n{")
    assert user.endswith("JOGADOR (Aria): tento passar sem ser visto")
    json.loads(user.split("\n")[1])  # o contexto é JSON válido


def test_feedback_lists_every_problem():
    msg = feedback_message(["a", "b"])
    assert msg["role"] == "user"
    assert "- a\n- b" in msg["content"]


def test_say_must_not_announce_the_outcome():
    # A fala é gerada antes da rolagem: se descrevesse o desfecho, o motor a desmentiria.
    assert "ANTES de o sistema resolver" in PROPOSER_SYSTEM
    assert "NUNCA" in PROPOSER_SYSTEM
    assert "acertou, falhou" in PROPOSER_SYSTEM


def test_missing_weapon_falls_back_instead_of_refusing():
    # Visto no qwen 4B: sem a arma citada, ele recusava o ataque em vez de usar os punhos.
    assert "NÃO recuse o ataque" in PROPOSER_SYSTEM


def test_a_target_that_is_not_listed_must_not_be_swapped_for_another():
    # Visto no nemotron: "ataco o sacerdote" (fora de vista) virava um ataque ao ferreiro, que
    # estava ali e nada tinha a ver. Sem alvo à vista, a proposta é vazia e o "say" explica.
    assert "NÃO ataque outro alvo no lugar dele" in PROPOSER_SYSTEM
    # a fala não distingue alvo escondido de inexistente (o servidor também não distingue)
    assert "sem afirmar se ele existe ou não" in PROPOSER_SYSTEM


def test_hidden_events_stay_out_of_the_prompt_and_the_last_five_are_still_five(
    campaign, rules, state
):
    events = [Event(turn=0, kind="x", text=f"evento {i}") for i in range(8)]
    state = state.model_copy(update={"events": events})
    assert build_context(campaign, rules, state, "aria")["eventos_recentes"] == [
        f"evento {i}" for i in range(3, 8)
    ]
    shown = build_context(campaign, rules, state, "aria", hide_events=frozenset({5, 7}))
    assert shown["eventos_recentes"] == ["evento 1", "evento 2", "evento 3", "evento 4", "evento 6"]
    messages = build_messages(campaign, rules, state, "aria", "oi", hide_events=frozenset({7}))
    assert "evento 7" not in messages[1]["content"]


def test_secrets_can_be_left_out_of_the_prompt(campaign, rules, state):
    here = move(state, campaign, to_location_id="floresta").state
    ruins = move(here, campaign, to_location_id="ruinas").state
    with_secrets = build_context(campaign, rules, ruins, "aria")
    assert with_secrets["npcs_aqui"][0]["segredos"] == ["Irmão Vael é o líder do culto."]
    without = build_context(campaign, rules, ruins, "aria", include_private=False)
    assert "segredos" not in without["npcs_aqui"][0]
    assert without["npcs_aqui"][0]["nome"] == "Irmão Vael"
    messages = build_messages(campaign, rules, ruins, "aria", "oi", include_private=False)
    assert "líder do culto" not in messages[1]["content"]


def test_a_revealed_fact_is_public_and_a_hidden_one_is_private(campaign, rules, state):
    with_notes = campaign.model_copy(
        update={
            "locations": [
                loc.model_copy(update={"private_notes": ["a vila esconde um poço"]})
                if loc.id == "vila"
                else loc
                for loc in campaign.locations
            ],
            "facts": [
                FactDef(id="culto", text="O culto é real."),
                FactDef(id="poco", text="O poço leva às ruínas."),
            ],
        }
    )
    revealed = reveal_fact(state, with_notes, fact_id="culto").state

    public = build_context(with_notes, rules, revealed, "aria", include_private=False)
    assert public["fatos_revelados"] == [{"sobre": None, "texto": "O culto é real."}]
    assert "privado" not in public
    flat = json.dumps(public, ensure_ascii=False)
    assert "O poço leva às ruínas." not in flat
    assert "a vila esconde um poço" not in flat

    private = build_context(with_notes, rules, revealed, "aria", include_private=True)
    assert private["fatos_revelados"] == public["fatos_revelados"]
    assert private["privado"] == ["a vila esconde um poço", "O poço leva às ruínas."]
    assert "O culto é real." not in private["privado"]


def test_a_revealed_fact_about_an_npc_names_who_it_is_about(campaign, rules, state):
    with_fact = campaign.model_copy(
        update={"facts": [FactDef(id="forja", text="Sabe forjar.", about="ferreiro")]}
    )
    revealed = reveal_fact(state, with_fact, fact_id="forja").state
    ctx = build_context(with_fact, rules, revealed, "aria", include_private=False)
    assert ctx["fatos_revelados"] == [{"sobre": "Bram", "texto": "Sabe forjar."}]
    hidden = build_context(with_fact, rules, state, "aria", include_private=True)
    assert hidden["npcs_aqui"][0]["segredos"] == ["Sabe forjar."]
    assert hidden["fatos_revelados"] == []
