import pytest

from devaneio.engine import EngineError, initial_state, move
from devaneio.schema import validate_against_campaign


@pytest.fixture
def state(campaign, rules):
    return initial_state(campaign, rules, 1)


def test_move_to_connected_location(state, campaign):
    result = move(state, campaign, to_location_id="floresta")
    assert state.current_location_id == "vila"
    assert state.events == []
    assert result.state.current_location_id == "floresta"
    assert (result.from_location_id, result.to_location_id) == ("vila", "floresta")
    assert result.text == "O grupo vai de Vila de Pedra Alta para Floresta Cinzenta."
    event = result.state.events[0]
    assert event.kind == "move"
    assert event.turn == 0
    assert event.text == result.text
    assert event.data == {"from_location_id": "vila", "to_location_id": "floresta"}
    assert validate_against_campaign(result.state, campaign) == []


def test_moves_chain_through_the_map(state, campaign):
    a = move(state, campaign, to_location_id="floresta").state
    b = move(a, campaign, to_location_id="ruinas").state
    c = move(b, campaign, to_location_id="floresta").state
    assert c.current_location_id == "floresta"
    assert [e.data["to_location_id"] for e in c.events] == ["floresta", "ruinas", "floresta"]


def test_cannot_skip_unconnected_locations(state, campaign):
    with pytest.raises(EngineError, match="'vila' não conecta a 'ruinas' \\(saídas: floresta\\)"):
        move(state, campaign, to_location_id="ruinas")


def test_unknown_destination(state, campaign):
    with pytest.raises(EngineError, match="local 'lua' não existe na campanha"):
        move(state, campaign, to_location_id="lua")


def test_already_there(state, campaign):
    with pytest.raises(EngineError, match="já está em 'vila'"):
        move(state, campaign, to_location_id="vila")


def test_current_location_missing_from_campaign(state, campaign):
    state.current_location_id = "limbo"
    with pytest.raises(EngineError, match="local atual 'limbo' não existe"):
        move(state, campaign, to_location_id="vila")
