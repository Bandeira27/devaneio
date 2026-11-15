"""Long-poll de eventos: espera por uma gravação da mesa, com teto de tempo e de esperas."""

import threading
import time
from itertools import count

import pytest

from conftest import CAMPAIGN_PATH
from devaneio.server import ApiFailure, Catalog, Storage, TableService
from devaneio.server.models import CommandRequest, CreateTableRequest, JoinRequest
from devaneio.server.storage import MAX_WAITERS

TOKENS = count(1)


@pytest.fixture
def service(tmp_path):
    return TableService(
        Catalog(CAMPAIGN_PATH.parent),
        Storage(tmp_path / "mesas", max_tables=10),
        token_source=lambda: f"token-{next(TOKENS)}",
        invite_source=lambda: "convite",
    )


@pytest.fixture
def table(service):
    created = service.create_table(
        CreateTableRequest(campaign_id="sombra-do-vale", host_name="Ana", seed=7)
    )
    joined = service.join_table(created.table_id, JoinRequest(invite_code="convite", name="Bia"))
    service.run_command(
        created.table_id,
        joined.token,
        CommandRequest(line='entrar bia "Bia"', revision=1),
    )
    return created.table_id, created.host_token, joined.token


def act(service, table_id, token, line):
    revision = service.get_table(table_id, token).revision
    return service.run_command(table_id, token, CommandRequest(line=line, revision=revision))


def run_in_thread(fn):
    box = {}

    def target():
        started = time.monotonic()
        try:
            box["result"] = fn()
        except Exception as exc:  # noqa: BLE001 — o teste devolve a falha da thread ao asserir
            box["error"] = exc
        box["elapsed"] = time.monotonic() - started

    thread = threading.Thread(target=target)
    thread.start()
    return thread, box


def test_a_waiting_reader_wakes_when_a_command_is_saved(service, table):
    table_id, _host, bia = table
    seen = service.get_table(table_id, bia).revision
    thread, box = run_in_thread(lambda: service.get_events(table_id, bia, seen, wait=10))
    act(service, table_id, bia, "testar lutar normal")
    thread.join(timeout=10)
    assert "error" not in box
    assert box["result"].events[0].kind == "check"
    assert box["result"].revision > seen
    assert box["elapsed"] < 5  # acordou pela gravação, não pelo prazo


def test_every_waiting_reader_wakes_on_one_write(service, table):
    table_id, host, bia = table
    seen = service.get_table(table_id, bia).revision
    readers = [
        run_in_thread(lambda token=token: service.get_events(table_id, token, seen, wait=10))
        for token in (bia, host, bia, host)
    ]
    act(service, table_id, bia, "testar lutar normal")
    for thread, box in readers:
        thread.join(timeout=10)
        assert "error" not in box
        assert box["result"].events
        assert box["elapsed"] < 5


def test_without_news_the_wait_ends_empty_after_the_deadline(service, table):
    table_id, _, bia = table
    seen = service.get_table(table_id, bia).revision
    started = time.monotonic()
    view = service.get_events(table_id, bia, seen, wait=0.3)
    assert time.monotonic() - started >= 0.25
    assert view.events == []
    assert view.revision == seen


def test_events_already_there_return_at_once_even_with_wait(service, table):
    table_id, _, bia = table
    started = time.monotonic()
    view = service.get_events(table_id, bia, 0, wait=10)
    assert time.monotonic() - started < 2
    assert view.events


def test_wait_zero_never_waits(service, table):
    table_id, _, bia = table
    seen = service.get_table(table_id, bia).revision
    started = time.monotonic()
    assert service.get_events(table_id, bia, seen, wait=0).events == []
    assert time.monotonic() - started < 1


def test_a_refused_or_read_only_command_does_not_wake_anyone(service, table):
    table_id, _host, bia = table
    seen = service.get_table(table_id, bia).revision
    thread, box = run_in_thread(lambda: service.get_events(table_id, bia, seen, wait=0.6))
    for line in ("olhar", "ficha"):
        act(service, table_id, bia, line)
    with pytest.raises(ApiFailure):
        act(service, table_id, bia, "fim")  # 403: nada foi gravado
    thread.join(timeout=10)
    assert box["result"].events == []
    assert box["elapsed"] >= 0.5  # esperou o prazo inteiro


def test_waiting_still_needs_a_valid_token_and_a_table(service, table):
    table_id, _, _ = table
    started = time.monotonic()
    for token in (None, "token-errado"):
        with pytest.raises(ApiFailure) as info:
            service.get_events(table_id, token, 0, wait=10)
        assert info.value.status == 401
    with pytest.raises(ApiFailure) as info:
        service.get_events("0123456789abcdef", "token-1", 0, wait=10)
    assert info.value.status == 404
    assert time.monotonic() - started < 2


def test_over_the_waiter_cap_the_answer_is_immediate(service, table):
    table_id, _, bia = table
    seen = service.get_table(table_id, bia).revision
    for _ in range(MAX_WAITERS):
        assert service.storage.enter_wait(table_id) is True
    started = time.monotonic()
    assert service.get_events(table_id, bia, seen, wait=10).events == []
    assert time.monotonic() - started < 2


def test_a_finished_wait_gives_its_slot_back(service, table):
    table_id, _, bia = table
    seen = service.get_table(table_id, bia).revision
    service.get_events(table_id, bia, seen, wait=0.1)
    # se a vaga não tivesse sido devolvida, só caberiam MAX_WAITERS - 1 agora
    assert [service.storage.enter_wait(table_id) for _ in range(MAX_WAITERS)] == [
        True
    ] * MAX_WAITERS
    assert service.storage.enter_wait(table_id) is False


def test_a_write_between_loading_and_waiting_is_not_slept_through(service, table, monkeypatch):
    """Gravação que cai entre a carga da visão e o início da espera: o leitor acorda na hora."""
    table_id, _, bia = table
    seen = service.get_table(table_id, bia).revision
    real_enter_wait = service.storage.enter_wait

    def enter_after_a_command(wanted_id):
        act(service, table_id, bia, "testar lutar normal")
        return real_enter_wait(wanted_id)

    monkeypatch.setattr(service.storage, "enter_wait", enter_after_a_command)
    started = time.monotonic()
    view = service.get_events(table_id, bia, seen, wait=5)
    assert view.events
    assert time.monotonic() - started < 2
