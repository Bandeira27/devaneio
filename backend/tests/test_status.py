import pytest

from devaneio.engine import (
    GameStatus,
    add_character,
    apply_damage,
    game_status,
    initial_state,
)
from devaneio.schema import BeatStatus


@pytest.fixture
def state(campaign, rules):
    s = initial_state(campaign, rules, 1)
    s = add_character(s, rules, character_id="aria", name="Aria").state
    return add_character(s, rules, character_id="zed", name="Zed").state


def down(state, campaign, who):
    return apply_damage(
        state, campaign, target_kind="character", target_id=who, amount=99, source="x"
    ).state


def test_active_by_default(state, campaign, rules):
    assert game_status(state) is GameStatus.ACTIVE
    assert game_status(initial_state(campaign, rules, 1)) is GameStatus.ACTIVE  # sem personagens


def test_lost_only_when_everyone_is_down(state, campaign):
    one = down(state, campaign, "aria")
    assert game_status(one) is GameStatus.ACTIVE
    assert game_status(down(one, campaign, "zed")) is GameStatus.LOST


def test_won_when_every_beat_is_done(state, campaign):
    s = state.model_copy(deep=True)
    s.beats = {b: BeatStatus.DONE for b in s.beats}
    assert game_status(s) is GameStatus.WON
    s.beats["pista"] = BeatStatus.FAILED
    assert game_status(s) is GameStatus.ACTIVE


def test_victory_beats_defeat(state, campaign):
    s = down(down(state, campaign, "aria"), campaign, "zed")
    s.beats = {b: BeatStatus.DONE for b in s.beats}
    assert game_status(s) is GameStatus.WON


def test_no_beats_never_wins(state):
    s = state.model_copy(deep=True)
    s.beats = {}
    assert game_status(s) is GameStatus.ACTIVE
