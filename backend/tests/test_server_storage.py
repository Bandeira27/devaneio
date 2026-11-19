"""Storage: mesas no banco, id gerado pelo servidor, limite atômico, um lock por mesa e gravações concorrentes."""

import re
import threading

import pytest

from conftest import make_storage
from devaneio.server import ApiFailure
from devaneio.server.storage import Record

ID_A = "0123456789abcdef"
ID_B = "fedcba9876543210"
ID_C = "00000000000000aa"


def record(n=0, campaign="sombra-do-vale.json"):
    return Record(campaign_path=campaign, state=f'{{"n": {n}}}', meta='{"m": 1}', content=None)


@pytest.fixture
def storage(tmp_path):
    return make_storage(tmp_path / "mesas", max_tables=3)


def test_new_table_id_has_the_generated_format(storage):
    assert re.fullmatch(r"[a-f0-9]{16}", storage.new_table_id())


def test_new_table_id_never_reuses_an_existing_id(storage, monkeypatch):
    storage.create(ID_A, record())
    ids = iter([ID_A, ID_B])
    monkeypatch.setattr("devaneio.server.storage.secrets.token_hex", lambda _n: next(ids))
    assert storage.new_table_id() == ID_B


def test_exists_and_read_only_serve_tables_that_exist(storage):
    assert storage.exists(ID_A) is False
    assert storage.read(ID_A) is None
    storage.create(ID_A, record(1))
    assert storage.exists(ID_A) is True
    assert storage.read(ID_A) == record(1)


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "../x",
        "ABCDEF0123456789",
        "0123456789abcde",
        "0123456789abcdefg",
        "0123456789abcdef\n",
        "x' OR '1'='1",
    ],
)
def test_an_id_outside_the_generated_format_never_reaches_the_database(storage, bad):
    assert storage.exists(bad) is False
    assert storage.read(bad) is None
    assert storage.delete(bad) is False


def test_save_replaces_the_record_and_stamps_the_time(tmp_path):
    clock = iter([100.0, 200.0])
    storage = make_storage(tmp_path / "m", max_tables=3, wall_clock=lambda: next(clock))
    storage.create(ID_A, record(1))
    storage.save(ID_A, record(2))
    assert storage.read(ID_A) == record(2)
    [summary] = storage.summaries("sombra-do-vale.json")
    assert summary.updated_at == 200.0


def test_save_of_a_table_that_was_deleted_is_404_and_does_not_bring_it_back(storage):
    storage.create(ID_A, record())
    storage.delete(ID_A)
    with pytest.raises(ApiFailure) as caught:
        storage.save(ID_A, record(9))
    assert caught.value.status == 404
    assert storage.exists(ID_A) is False


def test_delete_says_whether_the_table_existed(storage):
    storage.create(ID_A, record())
    assert storage.delete(ID_A) is True
    assert storage.delete(ID_A) is False


def test_the_table_limit_is_enforced_by_create(storage):
    for table_id in (ID_A, ID_B, ID_C):
        assert storage.create(table_id, record()) is True
    assert storage.create("1111111111111111", record()) is False
    assert storage.count() == 3
    assert storage.table_ids() == sorted([ID_A, ID_B, ID_C])


def test_concurrent_creations_never_pass_the_limit(tmp_path):
    storage = make_storage(tmp_path / "m", max_tables=3)
    results = []
    barrier = threading.Barrier(10)

    def create(index):
        barrier.wait()
        results.append(storage.create(f"{index:016x}", record(index)))

    threads = [threading.Thread(target=create, args=(i,)) for i in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    assert sorted(results) == [False] * 7 + [True] * 3
    assert storage.count() == 3


def test_summaries_and_campaigns_in_use_follow_the_campaign(storage):
    storage.create(ID_A, record(campaign="a.json"))
    storage.create(ID_B, record(campaign="b.json"))
    storage.create(ID_C, record(campaign="a.json"))
    assert [s.table_id for s in storage.summaries("a.json")] == [ID_C, ID_A]
    assert storage.summaries("nao-existe.json") == []
    assert storage.campaigns_in_use() == {"a.json", "b.json"}


def test_writers_on_different_tables_at_the_same_time_lose_nothing(tmp_path):
    storage = make_storage(tmp_path / "m", max_tables=20)
    ids = [f"{i:016x}" for i in range(8)]
    for table_id in ids:
        storage.create(table_id, record(0))
    errors = []
    barrier = threading.Barrier(len(ids))

    def play(table_id):
        try:
            barrier.wait()
            for n in range(1, 26):
                with storage.lock(table_id):  # o lock da mesa, como o servidor
                    storage.save(table_id, record(n))
        except Exception as exc:  # noqa: BLE001 — junta tudo e falha com a lista
            errors.append(exc)

    threads = [threading.Thread(target=play, args=(table_id,)) for table_id in ids]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(60)
    assert errors == []
    assert [storage.read(table_id).state for table_id in ids] == ['{"n": 25}'] * 8


def test_lock_is_one_object_per_table(storage):
    assert storage.lock(ID_A) is storage.lock(ID_A)
    assert storage.lock(ID_A) is not storage.lock(ID_B)


def test_the_say_cooldown_counts_down_per_player(tmp_path):
    now = [100.0]
    storage = make_storage(tmp_path, max_tables=2, clock=lambda: now[0])
    assert storage.slot_cooldown_left("t", "say", "p1", 30) == 0.0  # nunca falou
    storage.mark_slot("t", "say", "p1")
    assert storage.slot_cooldown_left("t", "say", "p1", 30) == 30.0
    assert storage.slot_cooldown_left("t", "say", "p2", 30) == 0.0  # outro jogador
    now[0] += 10
    assert storage.slot_cooldown_left("t", "say", "p1", 30) == 20.0
    now[0] += 25
    assert storage.slot_cooldown_left("t", "say", "p1", 30) == 0.0
