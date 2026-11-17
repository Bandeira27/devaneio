"""O desfecho (`outcome`) que o EventView leva ao selo do feed: só o grau, e só onde há selo."""

import json

import pytest

from conftest import CAMPAIGN_PATH
from devaneio.engine.checks import OUTCOME_LABELS
from devaneio.game import execute, new_game
from devaneio.rules import CheckOutcome
from devaneio.schema import Event
from devaneio.server.models import EventView
from devaneio.server.turns import (
    _ATTACK_OUTCOMES,
    _CHECK_OUTCOMES,
    events_view,
    outcome_of,
    text_of,
)


def event(kind, **data):
    return Event(turn=1, kind=kind, text="x", data=data)


@pytest.mark.parametrize(
    ("grade", "expected"),
    [
        ("critical_failure", "critical_failure"),
        ("failure", "failure"),
        ("success", "success"),
        ("critical_success", "critical_success"),
    ],
)
def test_a_check_keeps_its_degree(grade, expected):
    assert outcome_of(event("check", outcome=grade, attack=False)) == expected
    assert outcome_of(event("check", outcome=grade)) == expected  # eventos antigos sem `attack`


@pytest.mark.parametrize(
    ("grade", "expected"),
    [
        ("critical_failure", "critical_miss"),
        ("failure", "miss"),
        ("success", "hit"),
        ("critical_success", "critical_hit"),
    ],
)
def test_an_attack_check_says_hit_or_miss(grade, expected):
    assert outcome_of(event("check", outcome=grade, attack=True)) == expected


@pytest.mark.parametrize("data", [{}, {"outcome": "maravilha"}, {"outcome": 3}, {"outcome": None}])
def test_a_missing_or_unknown_degree_is_no_badge_instead_of_an_error(data):
    assert outcome_of(event("check", **data)) is None


def test_damage_and_heal_have_a_badge_and_the_other_kinds_do_not():
    assert outcome_of(event("damage", incapacitated=False)) == "damage"
    assert outcome_of(event("damage", incapacitated=True)) == "incapacitated"
    assert outcome_of(event("heal")) == "heal"
    for kind in ("move", "rest", "reveal", "turn_end", "director", "character_joined", "beat"):
        assert outcome_of(event(kind, outcome="success", incapacitated=True)) is None


@pytest.fixture
def session(tmp_path):
    base = new_game(CAMPAIGN_PATH, tmp_path / "p.json", seed=7)
    base, _ = execute(base, 'entrar bia "Bia" FOR=5')
    return base


def test_a_real_game_log_gets_the_badges_the_engine_logged(session):
    for line in ("bia: testar lutar normal", "bia: atacar punhos ferreiro", "ir floresta"):
        session, _ = execute(session, line)
    views = events_view(session, 0, role="host")
    by_kind = {}
    for view in views:
        by_kind.setdefault(view.kind, []).append(view.outcome)
    assert by_kind["move"] == [None]
    assert by_kind["check"][0] in {"critical_failure", "failure", "success", "critical_success"}
    assert by_kind["check"][1] in {"critical_miss", "miss", "hit", "critical_hit"}
    # com a semente 7 o ataque acerta; sem o `if`, o teste falha em vez de passar vazio se isso mudar
    assert by_kind["check"][1] in {"hit", "critical_hit"}
    assert by_kind["damage"][0] in {"damage", "incapacitated"}


def test_the_event_view_never_carries_the_dice_the_total_or_the_margin(session):
    session, _ = execute(session, "bia: testar lutar normal")
    check = events_view(session, 0, role="player")[-1]
    payload = check.model_dump()
    assert set(payload) == {"index", "turn", "kind", "text", "prose", "narration", "outcome"}
    state_data = session.state.events[-1].data
    sent = json.dumps(payload)
    for secret in ("rolls", "margin"):
        assert secret in state_data  # estava no estado...
        assert secret not in sent  # ...e não sai


def test_outcome_is_part_of_the_contract_and_nothing_else_was_added():
    assert list(EventView.model_fields) == [
        "index",
        "turn",
        "kind",
        "text",
        "prose",
        "narration",
        "outcome",
    ]
    assert EventView(index=0, turn=0, kind="move", text="t", prose="p").outcome is None


def test_every_engine_degree_has_a_test_and_an_attack_badge():

    degrees = {grade.value for grade in CheckOutcome}
    assert set(_CHECK_OUTCOMES) == degrees
    assert set(_ATTACK_OUTCOMES) == degrees


def test_a_hidden_npc_event_reaches_the_player_neither_with_text_nor_with_outcome(session):
    state, _ = execute(session, 'ferir sacerdote 2 "a"')  # o grupo está na vila: escondido
    host = {e.index: e.outcome for e in events_view(state, 0, role="host")}
    player = {e.index: e.outcome for e in events_view(state, 0, role="player")}
    assert host[2] == "damage"
    assert 2 not in player


def test_the_text_comes_without_the_outcome_the_badge_already_says(session):
    session, _ = execute(session, "bia: testar lutar normal")
    check = session.state.events[-1]
    label = OUTCOME_LABELS[CheckOutcome(check.data["outcome"])]
    assert check.text.endswith(f", {label}")  # o motor continua escrevendo a linha inteira
    sent = events_view(session, 0, role="host")[-1]
    assert sent.outcome is not None
    assert sent.text == check.text.removesuffix(f", {label}")
    session, _ = execute(session, 'ferir ferreiro 99 "x"')
    down = session.state.events[-1]
    assert down.text.endswith(", fora de combate")
    assert events_view(session, 0, role="host")[-1].text == down.text.removesuffix(
        ", fora de combate"
    )


@pytest.mark.parametrize("kind", ["move", "heal", "rest"])
def test_text_is_untouched_where_there_is_no_suffix_to_strip(kind):
    assert text_of(Event(turn=1, kind=kind, text="a, falha", data={})) == "a, falha"
    assert text_of(Event(turn=1, kind="damage", text="a, hp 5 → 3", data={})) == "a, hp 5 → 3"


def test_the_set_of_suffixes_is_the_engine_labels():
    assert set(OUTCOME_LABELS.values()) == {"falha crítica", "falha", "sucesso", "sucesso crítico"}
