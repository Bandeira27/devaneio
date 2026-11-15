from dataclasses import replace

import pytest

from conftest import CAMPAIGN_PATH
from devaneio.engine import (
    EngineError,
    direct,
    initial_state,
    move,
    reveal_fact,
    reveal_facts,
)
from devaneio.game import CommandError, execute, new_game
from devaneio.schema import AtLocation, FactDef, validate_against_campaign


def campaign_with(campaign, *facts):
    return campaign.model_copy(update={"facts": list(facts)})


AT_FOREST = [AtLocation(kind="at_location", location_id="floresta")]
SECRET = FactDef(id="trilha", text="Há uma trilha oculta.", about="ferreiro", reveal_when=AT_FOREST)
HOST_ONLY = FactDef(id="culto", text="O culto é real.")


@pytest.fixture
def state(campaign, rules):
    return initial_state(campaign, rules, rng_seed=5)


def test_a_fact_stays_hidden_until_its_conditions_hold(campaign, state):
    campaign = campaign_with(campaign, SECRET)
    same, texts = reveal_facts(state, campaign)
    assert same == state
    assert texts == ()

    moved = move(state, campaign, to_location_id="floresta").state
    revealed, texts = reveal_facts(moved, campaign)
    assert revealed.revealed_facts == {"trilha": moved.turn}
    assert texts == ("Revelado: Há uma trilha oculta.",)
    assert revealed.events[-1].kind == "reveal"
    assert revealed.events[-1].data == {"fact_id": "trilha"}
    assert validate_against_campaign(revealed, campaign) == []


def test_revealing_is_idempotent_and_does_not_mutate_the_input(campaign, state):
    campaign = campaign_with(campaign, SECRET)
    moved = move(state, campaign, to_location_id="floresta").state
    before = moved.model_copy(deep=True)
    once, _ = reveal_facts(moved, campaign)
    assert moved == before
    twice, texts = reveal_facts(once, campaign)
    assert twice == once
    assert texts == ()


def test_a_fact_without_conditions_is_never_revealed_by_the_engine(campaign, state):
    campaign = campaign_with(campaign, HOST_ONLY)
    same, texts = reveal_facts(state, campaign)
    assert same == state
    assert texts == ()


def test_the_host_reveals_a_fact_by_hand_once(campaign, state):
    campaign = campaign_with(campaign, HOST_ONLY)
    result = reveal_fact(state, campaign, fact_id="culto")
    assert result.state.revealed_facts == {"culto": state.turn}
    assert result.text == "Revelado: O culto é real."
    with pytest.raises(EngineError, match="já foi revelado"):
        reveal_fact(result.state, campaign, fact_id="culto")
    with pytest.raises(EngineError, match="não existe na campanha"):
        reveal_fact(state, campaign, fact_id="nada")


def test_the_director_reveals_facts(campaign, rules, state):
    campaign = campaign_with(campaign, SECRET)
    moved = move(state, campaign, to_location_id="floresta").state
    result = direct(moved, campaign, rules)
    assert "trilha" in result.state.revealed_facts
    assert "Revelado: Há uma trilha oculta." in result.actions


@pytest.fixture
def session(tmp_path, campaign):
    base = new_game(CAMPAIGN_PATH, tmp_path / "partida.json", seed=7)
    return replace(base, campaign=campaign_with(base.campaign, SECRET, HOST_ONLY))


def test_a_command_reveals_on_the_spot(session):
    session, _ = execute(session, 'entrar aria "Aria"')
    session, text = execute(session, "ir floresta")
    assert "Revelado: Há uma trilha oculta." in text
    assert "trilha" in session.state.revealed_facts


def test_fatos_and_revelar_commands(session):
    _, listing = execute(session, "fatos")
    assert "[oculto] Há uma trilha oculta. (trilha) sobre ferreiro" in listing
    session, text = execute(session, "revelar culto")
    assert text == "Revelado: O culto é real."
    _, listing = execute(session, "fatos")
    assert "[revelado] O culto é real. (culto)" in listing
    with pytest.raises(CommandError, match="uso: revelar"):
        execute(session, "revelar")
    with pytest.raises(CommandError, match="não existe"):
        execute(session, "revelar nada")


def test_fatos_without_facts(session):
    session = replace(session, campaign=campaign_with(session.campaign))
    assert execute(session, "fatos")[1] == "Nenhum fato na campanha."


def test_olhar_tells_what_the_group_already_knows(session):
    session, _ = execute(session, 'entrar aria "Aria"')
    assert "Vocês sabem" not in execute(session, "olhar")[1]
    session, _ = execute(session, "revelar culto")
    assert "Vocês sabem: O culto é real." in execute(session, "olhar")[1]


def test_a_new_game_already_reveals_facts_that_hold_at_the_start(tmp_path, campaign):
    here = [AtLocation(kind="at_location", location_id=campaign.start_location_id)]
    fact = FactDef(id="aqui", text="Já se sabe.", reveal_when=here)
    path = tmp_path / "c.json"
    path.write_text(campaign_with(campaign, fact).model_dump_json(), encoding="utf-8")
    session = new_game(path, tmp_path / "p.json", seed=3)
    assert "aqui" in session.state.revealed_facts
