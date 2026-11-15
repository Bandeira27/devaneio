"""Portão das chamadas de LLM da mesa: o esqueleto que o /say e o copiloto dividem."""

import pytest

from devaneio.server import ApiFailure, Storage
from devaneio.server.llm_gate import COPILOT, SAY, reserve


class Clock:
    now = 100.0

    def __call__(self):
        return self.now


@pytest.fixture
def clock():
    return Clock()


TABLE = "0123456789abcdef"


@pytest.fixture
def storage(tmp_path, clock):
    return Storage(tmp_path / "mesas", max_tables=2, clock=clock)


def refusal(storage, slot, key, cooldown):
    with pytest.raises(ApiFailure) as info:
        reserve(storage, TABLE, slot, key, cooldown)
    return info.value


def test_a_free_slot_is_reserved_and_counted(storage, clock):
    reserve(storage, TABLE, SAY, "p1", 30)
    assert storage.slot_cooldown_left(TABLE, "say", "p1", 30) == 30.0
    assert not storage.enter_slot(TABLE, "say")  # a vaga está ocupada


def test_busy_refuses_with_409_and_does_not_count_the_refused_one(storage):
    reserve(storage, TABLE, SAY, "p1", 0)
    failure = refusal(storage, SAY, "p2", 0)
    assert (failure.status, failure.code) == (409, "say_busy")
    assert storage.slot_cooldown_left(TABLE, "say", "p2", 30) == 0.0


def test_the_interval_refuses_with_429_and_keeps_the_slot_free(storage, clock):
    reserve(storage, TABLE, COPILOT, "mesa", 10)
    storage.leave_slot(TABLE, "copilot")
    failure = refusal(storage, COPILOT, "mesa", 10)
    assert (failure.status, failure.code) == (429, "copilot_rate_limited")
    assert "10 s" in failure.message
    assert storage.enter_slot(TABLE, "copilot")  # recusar por intervalo não reserva
    storage.leave_slot(TABLE, "copilot")
    clock.now += 11
    reserve(storage, TABLE, COPILOT, "mesa", 10)


def test_each_kind_has_its_own_slot_and_interval(storage):
    reserve(storage, TABLE, SAY, "p1", 30)
    reserve(storage, TABLE, COPILOT, "mesa", 30)  # o /say ocupado não segura o copiloto
    assert refusal(storage, SAY, "p1", 30).code == "say_rate_limited"
    assert refusal(storage, COPILOT, "mesa", 30).code == "copilot_rate_limited"
