import pytest

from devaneio.engine import EngineError, initial_state
from devaneio.rng import Rng
from devaneio.rules import RuleSystem, validate_state_against_rules
from devaneio.schema import BeatStatus, Character, validate_against_campaign


@pytest.fixture
def hero() -> Character:
    return Character(
        id="aria",
        name="Aria",
        attributes={"FOR": 2, "AGI": 3, "MEN": 1, "PRE": 2},
        hp=10,
        max_hp=10,
    )


def test_initial_state_is_coherent(campaign, rules, hero):
    state = initial_state(campaign, rules, 42, [hero])
    assert validate_against_campaign(state, campaign) == []
    assert validate_state_against_rules(state, rules) == []
    assert state.turn == 0
    assert state.rng_draws == 0
    assert state.rng_seed == 42
    assert state.current_location_id == campaign.start_location_id
    assert set(state.npcs) == {"ferreiro", "sacerdote"}
    assert state.npcs["sacerdote"].location_id == "ruinas"
    assert all(s is BeatStatus.PENDING for s in state.beats.values())
    assert state.characters == {"aria": hero}


def test_npc_attributes_merge_campaign_over_defaults(campaign, rules):
    state = initial_state(campaign, rules, 1)
    assert state.npcs["ferreiro"].attributes == {"FOR": 2, "AGI": 2, "MEN": 2, "PRE": 2}
    assert state.npcs["sacerdote"].attributes == {"FOR": 3, "AGI": 2, "MEN": 2, "PRE": 4}


def test_npc_hp_comes_from_max_hp_formula(campaign, rules):
    state = initial_state(campaign, rules, 1)
    assert rules.max_hp == "6 + FOR * 2"
    assert (state.npcs["ferreiro"].hp, state.npcs["ferreiro"].max_hp) == (10, 10)
    assert (state.npcs["sacerdote"].hp, state.npcs["sacerdote"].max_hp) == (12, 12)
    assert all(n.alive for n in state.npcs.values())
    assert (state.npcs["ferreiro"].disposition, state.npcs["sacerdote"].disposition) == (1, -3)


def test_dice_in_max_hp_consume_the_state_rng(campaign, rules_data):
    rules_data["max_hp"] = "1d6 + FOR"
    rules = RuleSystem.model_validate(rules_data)
    state = initial_state(campaign, rules, 7)
    rng = Rng(7)
    expected = [
        rng.roll(6) + 2,
        rng.roll(6) + 3,
    ]  # ferreiro FOR 2, sacerdote FOR 3 (ordem da campanha)
    assert [state.npcs["ferreiro"].max_hp, state.npcs["sacerdote"].max_hp] == expected
    assert state.rng_draws == 2
    assert initial_state(campaign, rules, 7) == state


def test_max_hp_below_one_is_an_error(campaign, rules_data):
    rules_data["max_hp"] = "FOR - 5"
    rules = RuleSystem.model_validate(rules_data)
    with pytest.raises(EngineError, match="max_hp de 'ferreiro' deu -3"):
        initial_state(campaign, rules, 1)
