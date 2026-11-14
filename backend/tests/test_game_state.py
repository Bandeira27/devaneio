import pytest
from pydantic import ValidationError

from devaneio.engine import initial_state
from devaneio.schema import (
    BeatStatus,
    Character,
    Event,
    Fact,
    GameState,
    NpcState,
    validate_against_campaign,
)


@pytest.fixture
def hero() -> Character:
    return Character(
        id="aria",
        name="Aria",
        attributes={"FOR": 2, "AGI": 1},
        hp=8,
        max_hp=10,
        inventory=["adaga"],
    )


@pytest.fixture
def state(campaign, rules, hero) -> GameState:
    return initial_state(campaign, rules, rng_seed=42, characters=[hero])


def test_json_roundtrip(state, campaign):
    state.facts.append(Fact(id="culto-existe", text="O culto é real.", turn=0))
    state.events.append(Event(turn=0, kind="narration", text="Vocês chegam à vila.", data={"x": 1}))
    text = state.model_dump_json()
    again = GameState.model_validate_json(text)
    assert again == state
    assert validate_against_campaign(again, campaign) == []
    assert '"pending"' in text  # enum serializa como string simples


def test_hp_above_max_is_rejected():
    with pytest.raises(ValidationError, match="maior que max_hp"):
        Character(id="x", name="X", hp=11, max_hp=10)


def test_negative_max_hp_is_rejected():
    with pytest.raises(ValidationError):
        Character(id="x", name="X", hp=0, max_hp=-1)


def test_npc_hp_above_max_is_rejected():
    with pytest.raises(ValidationError, match="maior que max_hp"):
        NpcState(hp=7, max_hp=6)


def test_character_key_must_match_id(state, hero):
    data = state.model_dump()
    data["characters"] = {"outro": hero.model_dump()}
    with pytest.raises(ValidationError, match="characters\\['outro'\\] tem id 'aria'"):
        GameState.model_validate(data)


def test_duplicate_fact_ids_are_rejected(state):
    data = state.model_dump()
    data["facts"] = [
        {"id": "f1", "text": "a", "turn": 0},
        {"id": "f1", "text": "b", "turn": 1},
    ]
    with pytest.raises(ValidationError, match="facts: id duplicado 'f1'"):
        GameState.model_validate(data)


def test_invalid_beat_status_is_rejected(state):
    data = state.model_dump()
    data["beats"]["chegada"] = "concluido"
    with pytest.raises(ValidationError):
        GameState.model_validate(data)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.__setitem__("turno", 3),
        lambda d: d["characters"]["aria"].__setitem__("mana", 5),
        lambda d: d["npcs"]["ferreiro"].__setitem__("vivo", True),
    ],
    ids=["root", "character", "npc_state"],
)
def test_unknown_fields_are_rejected(state, mutate):
    data = state.model_dump()
    mutate(data)
    with pytest.raises(ValidationError) as info:
        GameState.model_validate(data)
    assert info.value.errors()[0]["type"] == "extra_forbidden"


@pytest.mark.parametrize(
    ("mutate", "fragment"),
    [
        (lambda s: setattr(s, "campaign_id", "outra"), "referencia campanha 'outra'"),
        (lambda s: setattr(s, "current_location_id", "nada"), "current_location_id 'nada'"),
        (lambda s: s.npcs.__setitem__("intruso", s.npcs["ferreiro"]), "npc 'intruso' no estado"),
        (lambda s: s.npcs.pop("ferreiro"), "npc 'ferreiro' da campanha não tem estado"),
        (lambda s: s.beats.__setitem__("extra", BeatStatus.DONE), "marco 'extra' no estado"),
        (lambda s: s.beats.pop("pista"), "marco 'pista' da campanha não tem estado"),
        (lambda s: setattr(s.npcs["ferreiro"], "location_id", "nada"), "está em 'nada'"),
    ],
    ids=[
        "wrong_campaign",
        "missing_location",
        "extra_npc",
        "missing_npc",
        "extra_beat",
        "missing_beat",
        "npc_location",
    ],
)
def test_validate_against_campaign_reports_each_problem(state, campaign, mutate, fragment):
    mutate(state)
    errors = validate_against_campaign(state, campaign)
    assert len(errors) == 1
    assert fragment in errors[0]


def test_validate_against_campaign_reports_all_errors_together(state, campaign):
    state.campaign_id = "outra"
    state.npcs.pop("ferreiro")
    state.beats["extra"] = BeatStatus.DONE
    errors = validate_against_campaign(state, campaign)
    assert len(errors) == 3
