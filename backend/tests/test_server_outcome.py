"""O desfecho (`outcome`) que o EventView leva ao selo do feed: só o grau, e só onde há selo."""

import json

import pytest

from conftest import CAMPAIGN_PATH
from devaneio.game import execute, new_game
from devaneio.schema import Event
from devaneio.server.models import EventView
from devaneio.server.turns import events_view, outcome_of


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
    if "damage" in by_kind:  # o ataque só gera dano se acertou
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
