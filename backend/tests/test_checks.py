import pytest

from devaneio.engine import EngineError, classify_outcome, resolve_check
from devaneio.engine.checks import OUTCOME_LABELS
from devaneio.rng import Rng
from devaneio.rules import CheckOutcome, Outcomes
from devaneio.schema import Character, GameState, initial_state, validate_against_campaign

SEED = 2024


@pytest.fixture
def state(campaign) -> GameState:
    hero = Character(
        id="aria", name="Aria", attributes={"FOR": 2, "AGI": 3, "MEN": 1, "PRE": 2},
        hp=10, max_hp=10,
    )
    return initial_state(campaign, SEED, [hero])


def check(state, rules, **kw):
    kw.setdefault("character_id", "aria")
    kw.setdefault("skill_id", "lutar")
    kw.setdefault("difficulty_id", "normal")
    return resolve_check(state, rules, **kw)


def test_is_deterministic_and_pure(state, rules):
    a, b = check(state, rules), check(state, rules)
    assert a == b
    assert state.rng_draws == 0 and state.events == []


def test_advances_rng_and_logs_event(state, rules):
    result = check(state, rules)
    assert result.state.rng_draws == 2
    assert len(result.state.events) == 1
    event = result.state.events[0]
    assert event.kind == "check" and event.turn == state.turn and event.text == result.text
    assert event.data["outcome"] == result.outcome.value
    assert event.data["rolls"] == [{"dice": "2d6", "values": list(result.rolls[0].values)}]


def test_math_matches_rng_sequence(state, rules):
    rng = Rng(SEED)
    dice = [rng.roll(6), rng.roll(6)]
    result = check(state, rules)
    assert list(result.rolls[0].values) == dice
    assert result.total == sum(dice) + 2  # FOR
    assert result.difficulty == 9
    assert result.margin == result.total - 9
    assert result.outcome == classify_outcome(result.margin, rules.outcomes)


def test_consecutive_checks_continue_the_sequence(state, rules):
    first = check(state, rules)
    second = check(first.state, rules, skill_id="furtividade")
    rng = Rng(SEED)
    expected = [rng.roll(6) for _ in range(4)]
    assert list(first.rolls[0].values) + list(second.rolls[0].values) == expected
    assert second.state.rng_draws == 4 and len(second.state.events) == 2


def test_modifier_shifts_total(state, rules):
    plain = check(state, rules)
    adv = check(state, rules, modifier_id="vantagem")
    dis = check(state, rules, modifier_id="desvantagem")
    assert adv.total == plain.total + 2 and dis.total == plain.total - 2
    assert adv.rolls == plain.rolls  # mesmos dados: só o modificador muda
    assert "Vantagem" in adv.text and adv.state.events[0].data["modifier_id"] == "vantagem"


def test_text_is_narratable(state, rules):
    result = check(state, rules)
    assert result.text.startswith("Aria testa Lutar (2d6 + FOR) contra Normal 9: 2d6 [")
    assert f"total {result.total}, {OUTCOME_LABELS[result.outcome]}" in result.text


def test_resulting_state_roundtrips_and_stays_coherent(state, rules, campaign):
    result = check(state, rules, modifier_id="vantagem")
    again = GameState.model_validate_json(result.state.model_dump_json())
    assert again == result.state
    assert validate_against_campaign(again, campaign) == []


@pytest.mark.parametrize(
    "margin, outcome",
    [
        (-9, CheckOutcome.CRITICAL_FAILURE),
        (-5, CheckOutcome.CRITICAL_FAILURE),
        (-4, CheckOutcome.FAILURE),
        (-1, CheckOutcome.FAILURE),
        (0, CheckOutcome.SUCCESS),
        (4, CheckOutcome.SUCCESS),
        (5, CheckOutcome.CRITICAL_SUCCESS),
        (12, CheckOutcome.CRITICAL_SUCCESS),
    ],
)
def test_classify_outcome(margin, outcome):
    assert classify_outcome(margin, Outcomes(critical_failure_margin=-5, critical_success_margin=5)) is outcome


def test_every_degree_is_reachable_with_default_rules(state, rules):
    seen = set()
    current = state
    for _ in range(300):
        result = check(current, rules)
        seen.add(result.outcome)
        current = result.state
    assert seen == set(CheckOutcome)


@pytest.mark.parametrize(
    "kw, fragment",
    [
        ({"character_id": "ninguem"}, "personagem 'ninguem'"),
        ({"skill_id": "voar"}, "habilidade 'voar'"),
        ({"difficulty_id": "impossivel"}, "dificuldade 'impossivel'"),
        ({"modifier_id": "sorte"}, "modificador 'sorte'"),
    ],
)
def test_unknown_ids_raise(state, rules, kw, fragment):
    with pytest.raises(EngineError, match=fragment):
        check(state, rules, **kw)


def test_missing_attribute_on_character_raises(campaign, rules):
    hero = Character(id="zed", name="Zed", attributes={"AGI": 1}, hp=5, max_hp=5)
    state = initial_state(campaign, 1, [hero])
    with pytest.raises(EngineError, match="atributo 'FOR' não existe"):
        resolve_check(state, rules, character_id="zed", skill_id="lutar", difficulty_id="facil")
