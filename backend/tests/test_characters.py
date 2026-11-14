import pytest

from devaneio.engine import EngineError, add_character, initial_state
from devaneio.rng import Rng
from devaneio.rules import RuleSystem, validate_state_against_rules
from devaneio.schema import GameState, validate_against_campaign


@pytest.fixture
def state(campaign, rules):
    return initial_state(campaign, rules, 5)


def test_add_character_fills_defaults_and_hp(state, rules, campaign):
    result = add_character(
        state,
        rules,
        character_id="aria",
        name="Aria",
        attributes={"FOR": 3, "AGI": 1},
        inventory=["espada"],
    )
    assert state.characters == {} and state.events == []
    char = result.character
    assert char.attributes == {"FOR": 3, "AGI": 1, "MEN": 2, "PRE": 2}
    assert (char.hp, char.max_hp) == (12, 12)  # 6 + FOR * 2
    assert char.inventory == ["espada"]
    assert result.state.characters["aria"] == char
    assert result.text == "Aria entra na aventura (FOR 3, AGI 1, MEN 2, PRE 2; hp 12)."
    event = result.state.events[0]
    assert event.kind == "character_joined" and event.data["max_hp"] == 12
    assert validate_state_against_rules(result.state, rules) == []
    assert validate_against_campaign(result.state, campaign) == []
    assert result.state.rng_draws == 0


def test_no_attributes_means_all_defaults(state, rules):
    result = add_character(state, rules, character_id="zed", name="Zed")
    assert result.character.attributes == {"FOR": 2, "AGI": 2, "MEN": 2, "PRE": 2}
    assert result.character.max_hp == 10


def test_duplicate_id(state, rules):
    once = add_character(state, rules, character_id="aria", name="Aria").state
    with pytest.raises(EngineError, match="personagem 'aria' já existe"):
        add_character(once, rules, character_id="aria", name="Outra Aria")


def test_invalid_attributes_are_reported_together(state, rules):
    with pytest.raises(EngineError) as info:
        add_character(
            state, rules, character_id="x", name="X", attributes={"FOR": 9, "XIS": 1, "AGI": 0}
        )
    msg = str(info.value)
    assert msg.startswith("personagem 'x': ")
    assert "atributo 'XIS' não existe no sistema" in msg
    assert "FOR = 9 fora de [1, 5]" in msg and "AGI = 0 fora de [1, 5]" in msg


def test_invalid_id_is_an_engine_error(state, rules):
    with pytest.raises(EngineError, match="inválido"):
        add_character(state, rules, character_id="Aria Nova", name="Aria")


def test_dice_in_max_hp_consume_state_rng(campaign, rules_data):
    rules_data["max_hp"] = "2d6 + FOR"
    rules = RuleSystem.model_validate(rules_data)
    state = initial_state(campaign, rules, 11)  # dois NPCs: 4 sorteios
    assert state.rng_draws == 4
    result = add_character(state, rules, character_id="aria", name="Aria", attributes={"FOR": 3})
    rng = Rng(11, draws=4)
    assert result.character.max_hp == rng.roll(6) + rng.roll(6) + 3
    assert result.state.rng_draws == 6
    assert (
        add_character(state, rules, character_id="aria", name="Aria", attributes={"FOR": 3})
        == result
    )


def test_max_hp_below_one(state, rules_data):
    rules_data["max_hp"] = "FOR - 4"
    rules = RuleSystem.model_validate(rules_data)
    with pytest.raises(EngineError, match="max_hp de 'x' deu -2"):
        add_character(state, rules, character_id="x", name="X", attributes={"FOR": 2})


def test_initial_state_rejects_invalid_npc_attributes(campaign_data, rules):
    from devaneio.schema import Campaign

    campaign_data["npcs"][0]["attributes"] = {"FOR": 7}
    with pytest.raises(EngineError, match="npc 'ferreiro': FOR = 7 fora de \\[1, 5\\]"):
        initial_state(Campaign.model_validate(campaign_data), rules, 1)


def test_state_roundtrips_after_join(state, rules):
    result = add_character(state, rules, character_id="aria", name="Aria")
    assert GameState.model_validate_json(result.state.model_dump_json()) == result.state
