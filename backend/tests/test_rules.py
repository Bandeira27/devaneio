import pytest
from pydantic import ValidationError

from devaneio.engine import initial_state
from devaneio.rules import (
    RulesIntegrityError,
    RuleSystem,
    load_builtin_rules,
    load_rules,
    validate_campaign_against_rules,
    validate_rules,
    validate_state_against_rules,
)
from devaneio.schema import Campaign, Character


def errors_of(data: dict) -> list[str]:
    return validate_rules(RuleSystem.model_validate(data))


def test_default_system_loads_and_is_coherent():
    rules = load_builtin_rules("default")
    assert rules.id == "default"
    assert validate_rules(rules) == []
    assert {a.id for a in rules.attributes} == {"FOR", "AGI", "MEN", "PRE"}


def test_unknown_builtin_system():
    with pytest.raises(ValueError, match="não encontrado"):
        load_builtin_rules("inexistente")


def test_json_roundtrip(rules):
    again = RuleSystem.model_validate_json(rules.model_dump_json())
    assert again == rules
    assert load_rules(rules.model_dump_json()) == rules


@pytest.mark.parametrize(
    "collection", ["attributes", "difficulties", "skills", "weapons", "modifiers"]
)
def test_duplicate_ids_are_reported(rules_data, collection):
    rules_data[collection].append(dict(rules_data[collection][0]))
    dup = rules_data[collection][0]["id"]
    assert any(f"{collection}: id duplicado '{dup}'" in e for e in errors_of(rules_data))


@pytest.mark.parametrize(
    ("mutate", "fragment"),
    [
        (
            lambda d: d["skills"][0].__setitem__("formula", "2d6 + SOR"),
            "skill 'lutar': fórmula usa atributo 'SOR'",
        ),
        (
            lambda d: d["weapons"][0].__setitem__("damage", "1d4 + XIS"),
            "weapon 'punhos': fórmula usa atributo 'XIS'",
        ),
        (lambda d: d.__setitem__("max_hp", "6 + VIG * 2"), "max_hp: fórmula usa atributo 'VIG'"),
    ],
    ids=["skill", "weapon", "max_hp"],
)
def test_unknown_attribute_in_formula_is_reported(rules_data, mutate, fragment):
    mutate(rules_data)
    errors = errors_of(rules_data)
    assert len(errors) == 1
    assert fragment in errors[0]


def test_combat_references_must_exist(rules_data):
    rules_data["combat"] = {"attack_difficulty": "impossivel", "default_weapon": "canhao"}
    assert errors_of(rules_data) == [
        "combat.attack_difficulty 'impossivel' não existe",
        "combat.default_weapon 'canhao' não existe",
    ]


def test_npc_weapon_is_checked_against_rules(campaign_data, rules_data):
    campaign_data["npcs"][1]["weapon_id"] = "canhao"
    campaign = Campaign.model_validate(campaign_data)
    rules = RuleSystem.model_validate(rules_data)
    assert validate_campaign_against_rules(campaign, rules) == [
        "npc 'sacerdote': arma 'canhao' não existe no sistema"
    ]
    rules_data["combat"]["default_weapon"] = None
    campaign_data["npcs"][1]["weapon_id"] = None
    assert validate_campaign_against_rules(
        Campaign.model_validate(campaign_data), RuleSystem.model_validate(rules_data)
    ) == [
        "npc 'ferreiro' não tem arma e o sistema não define combat.default_weapon",
        "npc 'sacerdote' não tem arma e o sistema não define combat.default_weapon",
    ]


def test_rest_formula_is_checked(rules_data):
    rules_data["rest"]["heal"] = "1d6 + VIG"
    assert errors_of(rules_data) == ["rest.heal: fórmula usa atributo 'VIG', que não existe"]


def test_weapon_skill_must_exist(rules_data):
    rules_data["weapons"][0]["skill"] = "voar"
    assert errors_of(rules_data) == ["weapon 'punhos': habilidade 'voar' não existe"]


def test_syntax_error_in_formula_is_a_structural_error(rules_data):
    rules_data["skills"][0]["formula"] = "2d6 +"
    rules_data["max_hp"] = "6 / 2"
    with pytest.raises(ValidationError) as info:
        RuleSystem.model_validate(rules_data)
    messages = [e["msg"] for e in info.value.errors()]
    assert len(messages) == 2  # os dois erros reportados juntos
    assert all("fórmula inválida" in m for m in messages)


def test_attribute_default_must_be_within_range(rules_data):
    rules_data["attributes"][0]["default"] = 9
    with pytest.raises(ValidationError, match="fora do intervalo"):
        RuleSystem.model_validate(rules_data)


@pytest.mark.parametrize(("cf", "cs"), [(0, 5), (-5, 0), (3, 5), (-5, -1)])
def test_outcome_thresholds_must_bracket_zero(rules_data, cf, cs):
    rules_data["outcomes"] = {"critical_failure_margin": cf, "critical_success_margin": cs}
    with pytest.raises(ValidationError):
        RuleSystem.model_validate(rules_data)


@pytest.mark.parametrize("collection", ["attributes", "difficulties", "skills"])
def test_required_collections_cannot_be_empty(rules_data, collection):
    rules_data[collection] = []
    with pytest.raises(ValidationError):
        RuleSystem.model_validate(rules_data)


@pytest.mark.parametrize("bad", ["for", "Força", "1FOR", "FOR-2"])
def test_attribute_ids_are_uppercase_identifiers(rules_data, bad):
    rules_data["attributes"][0]["id"] = bad
    with pytest.raises(ValidationError):
        RuleSystem.model_validate(rules_data)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.__setitem__("dice", "2d6"),
        lambda d: d["skills"][0].__setitem__("attribute", "FOR"),
    ],
    ids=["root", "skill"],
)
def test_unknown_fields_are_rejected(rules_data, mutate):
    mutate(rules_data)
    with pytest.raises(ValidationError) as info:
        RuleSystem.model_validate(rules_data)
    assert info.value.errors()[0]["type"] == "extra_forbidden"


def test_load_rules_raises_with_full_error_list(rules_data):
    rules_data["max_hp"] = "VIG"
    rules_data["weapons"].append(dict(rules_data["weapons"][0]))
    with pytest.raises(RulesIntegrityError) as info:
        load_rules(rules_data)
    assert len(info.value.errors) == 2


def _hero(**attributes) -> Character:
    return Character(id="aria", name="Aria", attributes=attributes, hp=10, max_hp=10)


def test_state_matching_rules_has_no_errors(campaign, rules):
    state = initial_state(campaign, rules, 1, [_hero(FOR=2, AGI=3, MEN=1, PRE=2)])
    assert validate_state_against_rules(state, rules) == []


def test_state_against_rules_reports_each_problem(campaign, rules):
    state = initial_state(campaign, rules, 1, [_hero(FOR=9, AGI=3, PRE=2, XIS=1)])
    errors = validate_state_against_rules(state, rules)
    assert errors == [
        "personagem 'aria' não tem o atributo 'MEN'",
        "personagem 'aria' tem atributo 'XIS', que o sistema não declara",
        "personagem 'aria': FOR = 9 fora de [1, 5]",
    ]


def test_npc_attributes_in_state_are_checked_too(campaign, rules):
    state = initial_state(campaign, rules, 1)
    state.npcs["ferreiro"].attributes["FOR"] = 0
    assert validate_state_against_rules(state, rules) == ["npc 'ferreiro': FOR = 0 fora de [1, 5]"]


def test_campaign_matching_rules_has_no_errors(campaign, rules):
    assert validate_campaign_against_rules(campaign, rules) == []


def test_campaign_against_rules_reports_each_problem(campaign_data, rules):
    campaign_data["rules_id"] = "outro"
    campaign_data["npcs"][1]["attributes"] = {
        "FOR": 7,
        "XIS": 1,
    }  # parcial é permitido, inválido não
    errors = validate_campaign_against_rules(Campaign.model_validate(campaign_data), rules)
    assert errors == [
        "campanha pede o sistema 'outro', mas o sistema é 'default'",
        "npc 'sacerdote' tem atributo 'XIS', que o sistema não declara",
        "npc 'sacerdote': FOR = 7 fora de [1, 5]",
    ]


def test_fallen_can_act_comes_from_the_rules_data_and_defaults_to_false():
    data = load_builtin_rules("default").model_dump(mode="json")
    assert data["combat"]["fallen_can_act"] is False
    del data["combat"]["fallen_can_act"]  # o campo é opcional: um arquivo antigo continua válido
    assert RuleSystem.model_validate(data).combat.fallen_can_act is False
    data["combat"]["fallen_can_act"] = True
    assert RuleSystem.model_validate(data).combat.fallen_can_act is True
