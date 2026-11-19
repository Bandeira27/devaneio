"""Exibição em memória: narração por evento, mural de falas e o que o reinício preserva."""

import threading
import time

import pytest

from conftest import CAMPAIGN_PATH, make_storage, open_for_play
from devaneio.server import Catalog, TableService
from devaneio.server.models import CreateTableRequest, JoinRequest
from devaneio.server.presentation import MAX_NARRATIONS, MAX_TALK, Presentation


def test_narrations_keep_only_the_latest():
    presentation = Presentation(0)
    presentation.store_narrations({i: f"n{i}" for i in range(MAX_NARRATIONS + 3)})
    kept = presentation.narrations()
    assert len(kept) == MAX_NARRATIONS
    assert min(kept) == 3
    assert presentation.narrations() is not presentation.narrations()  # uma cópia a cada leitura


def test_talk_is_numbered_in_order_filtered_by_seq_and_capped():
    presentation = Presentation(1000)
    first = presentation.add_talk(after=4, to="bia", text="um")
    second = presentation.add_talk(after=5, to="ana", text="dois")
    assert (first.seq, second.seq) == (1001, 1002)
    talk, last = presentation.talk_since(0)
    assert [t.text for t in talk] == ["um", "dois"]
    assert last == 1002
    assert presentation.talk_since(1001)[0] == [second]
    assert presentation.talk_since(1002) == ([], 1002)
    for number in range(MAX_TALK + 5):
        presentation.add_talk(after=0, to="bia", text=f"t{number}")
    assert len(presentation.talk_since(0)[0]) == MAX_TALK


def test_the_talk_numbers_start_from_the_wall_clock_so_a_restart_keeps_climbing(tmp_path):
    table = "0123456789abcdef"
    before = make_storage(tmp_path, max_tables=2, wall_clock=lambda: 1_700_000_000.0)
    first = before.presentation(table).add_talk(after=0, to="bia", text="antes")
    after_restart = make_storage(tmp_path, max_tables=2, wall_clock=lambda: 1_700_000_060.0)
    later = after_restart.presentation(table).add_talk(after=0, to="bia", text="depois")
    assert first.seq == 1_700_000_000_000 + 1
    assert later.seq > first.seq  # quem leu `first` não perde `later`


def test_the_storage_clock_is_the_one_the_long_poll_deadline_uses(tmp_path):
    now = [50.0]
    storage = make_storage(tmp_path, max_tables=2, clock=lambda: now[0])
    assert storage.now() == 50.0
    now[0] = 80.0
    assert storage.now() == 80.0


# --- um cliente que não devolve since_talk não gira sem esperar --------------------


@pytest.fixture
def service(tmp_path):
    return TableService(
        Catalog(CAMPAIGN_PATH.parent),
        make_storage(tmp_path / "mesas", max_tables=2),
        token_source=iter(f"token-{n}" for n in range(1, 50)).__next__,
        invite_source=lambda: "convite",
    )


def test_wait_without_since_talk_does_not_return_at_once_for_old_talk(service):
    created = service.create_table(
        CreateTableRequest(campaign_id="sombra-do-vale", host_name="Ana", seed=7)
    )
    open_for_play(service, created.table_id)
    table_id, host = created.table_id, created.host_token
    service.storage.presentation(table_id).add_talk(after=1, to="ana", text="antiga")
    revision = service.get_table(table_id, host).revision
    started = time.monotonic()
    view = service.get_events(table_id, host, revision, wait=0.4)  # sem since_talk
    assert time.monotonic() - started >= 0.35  # esperou: a fala antiga não é novidade
    assert view.talk == []
    assert view.talk_seq > 0  # mas o cliente fica sabendo de onde continuar


def test_wait_without_since_talk_wakes_for_a_new_talk_and_returns_only_that(service):
    created = service.create_table(
        CreateTableRequest(campaign_id="sombra-do-vale", host_name="Ana", seed=7)
    )
    open_for_play(service, created.table_id)
    table_id, host = created.table_id, created.host_token
    joined = service.join_table(table_id, JoinRequest(invite_code="convite", name="Bia"))
    presentation = service.storage.presentation(table_id)
    presentation.add_talk(after=1, to="ana", text="antiga")
    revision = service.get_table(table_id, host).revision
    box = {}

    def poll():
        box["view"] = service.get_events(table_id, joined.token, revision, wait=10)

    thread = threading.Thread(target=poll)
    thread.start()
    deadline = time.monotonic() + 10
    while service.storage.waiting(table_id) == 0:  # espera pelo estado, não pelo relógio
        assert time.monotonic() < deadline
        time.sleep(0.005)
    presentation.add_talk(after=1, to="ana", text="nova")
    with service.storage.lock(table_id):
        service.storage.announce_change(table_id)
    thread.join(timeout=10)
    assert [t.text for t in box["view"].talk] == ["nova"]


def test_waiting_counts_the_pollers_of_a_table(tmp_path):
    storage = make_storage(tmp_path, max_tables=2)
    table = "0123456789abcdef"
    assert storage.waiting(table) == 0
    assert storage.enter_wait(table) is True
    assert storage.waiting(table) == 1
    storage.leave_wait(table)
    assert storage.waiting(table) == 0
