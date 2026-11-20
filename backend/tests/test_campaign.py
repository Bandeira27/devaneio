import pytest
from pydantic import ValidationError

from devaneio.schema import (
    Campaign,
    CampaignIntegrityError,
    load_campaign,
    validate_campaign,
)


def errors_of(data: dict) -> list[str]:
    return validate_campaign(Campaign.model_validate(data))


def test_fixture_is_valid(campaign):
    assert validate_campaign(campaign) == []


def test_json_roundtrip(campaign):
    text = campaign.model_dump_json()
    again = Campaign.model_validate_json(text)
    assert again == campaign
    assert validate_campaign(again) == []
    assert again.schema_version == 1
    assert again.rules_id == "default"


def test_load_campaign_accepts_json_text_and_dict(campaign_data, campaign):
    assert load_campaign(campaign_data) == campaign
    assert load_campaign(campaign.model_dump_json()) == campaign


@pytest.mark.parametrize("collection", ["locations", "factions", "npcs", "beats", "facts"])
def test_duplicate_ids_are_reported(campaign_data, collection):
    campaign_data[collection].append(dict(campaign_data[collection][0]))
    dup = campaign_data[collection][0]["id"]
    errors = errors_of(campaign_data)
    assert any(f"{collection}: id duplicado '{dup}'" in e for e in errors)


@pytest.mark.parametrize(
    ("mutate", "fragment"),
    [
        (lambda d: d["locations"][0]["connections"].append("nada"), "conecta a 'nada'"),
        (lambda d: d["npcs"][0].__setitem__("location_id", "nada"), "está em 'nada'"),
        (lambda d: d["npcs"][0].__setitem__("faction_id", "nada"), "pertence a 'nada'"),
        (lambda d: d.__setitem__("start_location_id", "nada"), "start_location_id 'nada'"),
        (lambda d: d["beats"][1]["requires"].append("nada"), "requer 'nada'"),
    ],
    ids=["connection", "npc_location", "npc_faction", "start_location", "beat_requires"],
)
def test_missing_references_are_reported(campaign_data, mutate, fragment):
    mutate(campaign_data)
    errors = errors_of(campaign_data)
    assert len(errors) == 1
    assert fragment in errors[0]


def test_self_connection_is_reported(campaign_data):
    campaign_data["locations"][0]["connections"].append("vila")
    assert errors_of(campaign_data) == ["local 'vila' conecta a si mesmo"]


def test_direct_cycle_between_beats(campaign_data):
    campaign_data["beats"][0]["requires"] = ["pista"]  # chegada <-> pista
    errors = errors_of(campaign_data)
    assert len(errors) == 1
    assert errors[0].startswith("ciclo entre marcos:")
    assert "chegada" in errors[0]
    assert "pista" in errors[0]


def test_indirect_cycle_between_beats(campaign_data):
    campaign_data["beats"][0]["requires"] = [
        "confronto"
    ]  # chegada -> confronto -> pista -> chegada
    errors = errors_of(campaign_data)
    assert errors == ["ciclo entre marcos: chegada -> confronto -> pista -> chegada"]


def test_self_requirement_is_reported_once(campaign_data):
    campaign_data["beats"][0]["requires"] = ["chegada"]
    assert errors_of(campaign_data) == ["marco 'chegada' requer a si mesmo"]


def test_unknown_field_at_root_is_rejected(campaign_data):
    campaign_data["premisse"] = "typo"
    with pytest.raises(ValidationError) as info:
        Campaign.model_validate(campaign_data)
    assert info.value.errors()[0]["type"] == "extra_forbidden"


def test_unknown_field_in_nested_model_is_rejected(campaign_data):
    campaign_data["locations"][0]["conections"] = []
    with pytest.raises(ValidationError) as info:
        Campaign.model_validate(campaign_data)
    assert info.value.errors()[0]["type"] == "extra_forbidden"


@pytest.mark.parametrize("bad_id", ["Vila", "vila nova", "-vila", "vilã", ""])
def test_id_must_be_slug(campaign_data, bad_id):
    campaign_data["id"] = bad_id
    with pytest.raises(ValidationError):
        Campaign.model_validate(campaign_data)


def test_all_errors_are_reported_together(campaign_data):
    campaign_data["start_location_id"] = "nada"
    campaign_data["locations"].append(dict(campaign_data["locations"][0]))
    campaign_data["npcs"][0]["faction_id"] = "ninguem"
    campaign_data["beats"][0]["requires"] = ["pista"]
    errors = errors_of(campaign_data)
    assert len(errors) == 4
    joined = "\n".join(errors)
    assert "start_location_id 'nada'" in joined
    assert "locations: id duplicado 'vila'" in joined
    assert "pertence a 'ninguem'" in joined
    assert "ciclo entre marcos" in joined


def test_load_campaign_raises_with_full_error_list(campaign_data):
    campaign_data["start_location_id"] = "nada"
    campaign_data["npcs"][0]["location_id"] = "nada"
    with pytest.raises(CampaignIntegrityError) as info:
        load_campaign(campaign_data)
    assert len(info.value.errors) == 2
    assert "Campanha inconsistente" in str(info.value)


@pytest.mark.parametrize(
    ("cond", "fragment"),
    [
        ({"kind": "at_location", "location_id": "lua"}, "local 'lua' não existe"),
        ({"kind": "npc_down", "npc_id": "ninguem"}, "npc 'ninguem' não existe"),
        ({"kind": "beat_done", "beat_id": "nada"}, "marco 'nada' não existe"),
        ({"kind": "beat_done", "beat_id": "pista"}, "depende da própria conclusão"),
    ],
)
def test_condition_references_are_checked(campaign_data, cond, fragment):
    campaign_data["beats"][1]["complete_when"] = [cond]
    errors = errors_of(campaign_data)
    assert len(errors) == 1
    assert errors[0].startswith("marco 'pista', complete_when: ")
    assert fragment in errors[0]


def test_fact_about_an_unknown_element_is_reported(campaign_data):
    campaign_data["facts"][0]["about"] = "ninguem"
    errors = errors_of(campaign_data)
    assert errors == ["fato 'ferreiro-segredo' fala de 'ninguem', que não existe"]


def test_fact_reveal_conditions_are_checked_like_beats(campaign_data):
    campaign_data["facts"][0]["reveal_when"] = [{"kind": "npc_down", "npc_id": "ninguem"}]
    errors = errors_of(campaign_data)
    assert errors == ["fato 'ferreiro-segredo', reveal_when: npc 'ninguem' não existe"]


def test_unknown_condition_kind_is_a_structural_error(campaign_data):
    campaign_data["beats"][0]["activate_when"] = [{"kind": "full_moon"}]
    with pytest.raises(ValidationError):
        Campaign.model_validate(campaign_data)


def test_example_campaign_has_triggers(campaign):
    by_id = {b.id: b for b in campaign.beats}
    # chegada só fecha com o grupo na vila e a conversa vencida (persuadir)
    assert by_id["chegada"].complete_when[0].location_id == "vila"
    assert by_id["chegada"].complete_when[1].skill_id == "persuadir"
    assert by_id["pista"].complete_when[0].location_id == "ruinas"
    assert by_id["pista"].complete_when[1].skill_id == "investigar"
    assert by_id["confronto"].complete_when[1].npc_id == "sacerdote"


def test_example_facts_are_revealed_by_conditions(campaign):
    by_id = {f.id: f for f in campaign.facts}
    assert [c.kind for c in by_id["ferreiro-segredo"].reveal_when] == [
        "at_location",
        "check_passed",
    ]
    assert [c.kind for c in by_id["sacerdote-segredo"].reveal_when] == ["at_location", "npc_down"]


@pytest.mark.parametrize("about", ["vila", "culto", "sacerdote", "chegada"])
def test_fact_about_any_known_element_is_valid(campaign_data, about):
    campaign_data["facts"][0]["about"] = about
    assert errors_of(campaign_data) == []


def test_fact_reveal_conditions_reject_unknown_beat_and_location(campaign_data):
    campaign_data["facts"][0]["reveal_when"] = [
        {"kind": "beat_done", "beat_id": "nada"},
        {"kind": "at_location", "location_id": "lugar"},
    ]
    assert errors_of(campaign_data) == [
        "fato 'ferreiro-segredo', reveal_when: marco 'nada' não existe",
        "fato 'ferreiro-segredo', reveal_when: local 'lugar' não existe",
    ]


def test_narration_id_defaults_to_the_builtin_pack(campaign_data):
    assert "narration_id" not in campaign_data
    assert Campaign.model_validate(campaign_data).narration_id == "pt-br"
    campaign_data["narration_id"] = "meu-estilo"
    assert Campaign.model_validate(campaign_data).narration_id == "meu-estilo"
