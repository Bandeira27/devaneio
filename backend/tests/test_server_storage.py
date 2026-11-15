"""Storage: id gerado pelo servidor, caminho sempre dentro da pasta de dados, um lock por mesa."""

import re

import pytest

from devaneio.server import Storage

ID_A = "0123456789abcdef"
ID_B = "fedcba9876543210"


@pytest.fixture
def storage(tmp_path):
    return Storage(tmp_path / "mesas", max_tables=3)


def test_new_table_path_has_the_generated_format_inside_the_data_folder(storage):
    table_id, path = storage.new_table_path()
    assert re.fullmatch(r"[a-f0-9]{16}", table_id)
    assert path == storage.data_dir / f"{table_id}.json"
    assert path.exists() is False


def test_new_table_path_never_reuses_an_existing_id(storage, monkeypatch):
    (storage.data_dir / f"{ID_A}.json").write_text("{}", encoding="utf-8")
    ids = iter([ID_A, ID_B])
    monkeypatch.setattr("devaneio.server.storage.secrets.token_hex", lambda _n: next(ids))
    table_id, path = storage.new_table_path()
    assert table_id == ID_B
    assert path == storage.data_dir / f"{ID_B}.json"


def test_path_for_only_resolves_tables_that_exist(storage):
    assert storage.path_for(ID_A) is None
    (storage.data_dir / f"{ID_A}.json").write_text("{}", encoding="utf-8")
    assert storage.path_for(ID_A) == storage.data_dir / f"{ID_A}.json"


def test_count_ignores_files_that_are_not_tables(storage):
    (storage.data_dir / f"{ID_A}.json").write_text("{}", encoding="utf-8")
    (storage.data_dir / "anotacoes.json").write_text("{}", encoding="utf-8")
    (storage.data_dir / f"{ID_B}.txt").write_text("", encoding="utf-8")
    assert storage.count() == 1


def test_lock_is_one_object_per_table(storage):
    assert storage.lock(ID_A) is storage.lock(ID_A)
    assert storage.lock(ID_A) is not storage.lock(ID_B)


def test_the_say_cooldown_counts_down_per_player(tmp_path):
    now = [100.0]
    storage = Storage(tmp_path, max_tables=2, clock=lambda: now[0])
    assert storage.slot_cooldown_left("t", "say", "p1", 30) == 0.0  # nunca falou
    storage.mark_slot("t", "say", "p1")
    assert storage.slot_cooldown_left("t", "say", "p1", 30) == 30.0
    assert storage.slot_cooldown_left("t", "say", "p2", 30) == 0.0  # outro jogador
    now[0] += 10
    assert storage.slot_cooldown_left("t", "say", "p1", 30) == 20.0
    now[0] += 25
    assert storage.slot_cooldown_left("t", "say", "p1", 30) == 0.0
