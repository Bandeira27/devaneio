import pytest

from devaneio.engine import EngineError, activate_beat, complete_beat, fail_beat, initial_state
from devaneio.schema import BeatStatus, GameState


@pytest.fixture
def state(campaign, rules) -> GameState:
    return initial_state(campaign, rules, 1)


def test_activate_then_complete(state, campaign):
    a = activate_beat(state, campaign, beat_id="chegada")
    assert state.beats["chegada"] is BeatStatus.PENDING and state.events == []
    assert a.state.beats["chegada"] is BeatStatus.ACTIVE
    assert a.text == "Marco ativado: Chegada à vila."
    assert a.state.events[-1].kind == "beat_activated"
    assert a.state.events[-1].data == {"beat_id": "chegada", "status": "active"}

    d = complete_beat(a.state, campaign, beat_id="chegada")
    assert d.state.beats["chegada"] is BeatStatus.DONE
    assert d.text == "Marco concluído: Chegada à vila."
    assert [e.kind for e in d.state.events] == ["beat_activated", "beat_done"]


def test_fail(state, campaign):
    a = activate_beat(state, campaign, beat_id="chegada").state
    f = fail_beat(a, campaign, beat_id="chegada")
    assert f.state.beats["chegada"] is BeatStatus.FAILED
    assert f.text == "Marco falhou: Chegada à vila."


def test_requirements_must_be_done(state, campaign):
    with pytest.raises(EngineError, match="marco 'pista' exige concluídos: chegada"):
        activate_beat(state, campaign, beat_id="pista")
    done = complete_beat(
        activate_beat(state, campaign, beat_id="chegada").state, campaign, beat_id="chegada"
    ).state
    assert activate_beat(done, campaign, beat_id="pista").state.beats["pista"] is BeatStatus.ACTIVE


def test_failed_requirement_blocks(state, campaign):
    failed = fail_beat(
        activate_beat(state, campaign, beat_id="chegada").state, campaign, beat_id="chegada"
    ).state
    with pytest.raises(EngineError, match="exige concluídos: chegada"):
        activate_beat(failed, campaign, beat_id="pista")


@pytest.mark.parametrize(
    "action, fragment",
    [
        (complete_beat, "está 'pending', precisava estar 'active'"),
        (fail_beat, "está 'pending', precisava estar 'active'"),
    ],
)
def test_wrong_status(state, campaign, action, fragment):
    with pytest.raises(EngineError, match=fragment):
        action(state, campaign, beat_id="chegada")


def test_activate_twice(state, campaign):
    a = activate_beat(state, campaign, beat_id="chegada").state
    with pytest.raises(EngineError, match="está 'active', precisava estar 'pending'"):
        activate_beat(a, campaign, beat_id="chegada")


def test_unknown_beat(state, campaign):
    with pytest.raises(EngineError, match="marco 'nada' não existe na campanha"):
        activate_beat(state, campaign, beat_id="nada")
    state.beats.pop("chegada")
    with pytest.raises(EngineError, match="marco 'chegada' não está no estado"):
        activate_beat(state, campaign, beat_id="chegada")
