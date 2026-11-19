"""O banco do servidor: arquivo protegido, transações curtas, concorrência e a premissa de um processo só."""

import os
import sqlite3
import stat
import threading
import time
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from devaneio.server.database import (
    DB_NAME,
    Database,
    StorageBusy,
    acquire_instance_lock,
)
from devaneio.server.errors import DatabaseError
from devaneio.server.files import prepare_data_dir
from devaneio.server.migrations import migrate

posix_only = pytest.mark.skipif(os.name != "posix", reason="modos POSIX")


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


@pytest.fixture
def db(tmp_path):
    database = Database(prepare_data_dir(tmp_path / "dados") / DB_NAME)
    migrate(database)
    yield database
    database.close()


def get(db, key):
    return db.read(
        lambda s: s.execute(text("SELECT value FROM settings WHERE key = :k"), {"k": key}).scalar()
    )


def put(session, key, value):
    session.execute(
        text(
            "INSERT INTO settings (key, value) VALUES (:k, :v) ON CONFLICT(key) DO UPDATE SET value = :v"
        ),
        {"k": key, "v": value},
    )


# --- permissões -----------------------------------------------------------------------


@posix_only
def test_data_dir_and_database_files_are_private(db):
    db.write(lambda s: put(s, "a", "1"))
    folder = db.path.parent
    assert mode(folder) == 0o700
    assert mode(db.path) == 0o600
    for suffix in ("-wal", "-shm"):
        side = Path(f"{db.path}{suffix}")
        assert side.exists()
        assert mode(side) == 0o600


@posix_only
def test_open_data_dir_is_closed_with_a_warning(tmp_path, capsys):
    folder = tmp_path / "abertos"
    folder.mkdir()
    folder.chmod(0o755)
    prepare_data_dir(folder)
    assert mode(folder) == 0o700
    assert "fechei" in capsys.readouterr().err


@posix_only
def test_open_database_file_is_closed_with_a_warning(tmp_path, capsys):
    folder = prepare_data_dir(tmp_path / "d")
    (folder / DB_NAME).touch()
    (folder / DB_NAME).chmod(0o644)
    Database(folder / DB_NAME).close()
    assert mode(folder / DB_NAME) == 0o600
    assert "fechei" in capsys.readouterr().err


@posix_only
def test_folder_owned_by_someone_else_is_refused(tmp_path, monkeypatch):
    folder = tmp_path / "alheia"
    folder.mkdir()
    monkeypatch.setattr(os, "getuid", lambda: os.stat(folder).st_uid + 1)
    with pytest.raises(DatabaseError, match="outro usuário"):
        prepare_data_dir(folder)


# --- um processo por banco ------------------------------------------------------------


@posix_only
def test_second_instance_on_the_same_folder_is_refused(tmp_path):
    folder = prepare_data_dir(tmp_path / "d")
    first = acquire_instance_lock(folder)
    assert first is not None
    with pytest.raises(DatabaseError, match="um banco, um servidor"):
        acquire_instance_lock(folder)
    first.close()
    again = acquire_instance_lock(folder)
    assert again is not None
    again.close()


# --- concorrência ---------------------------------------------------------------------


def run_threads(count, target):
    errors = []
    barrier = threading.Barrier(count)

    def wrapper(index):
        try:
            barrier.wait()
            target(index)
        except Exception as exc:  # noqa: BLE001 — o teste junta tudo e falha com a lista
            errors.append(exc)

    threads = [threading.Thread(target=wrapper, args=(i,)) for i in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    return errors


def test_writers_on_different_rows_never_see_locked(db):
    def work(index):
        for _ in range(25):
            db.write(
                lambda s, index=index: put(
                    s, f"mesa-{index}", str(int(_value(s, f"mesa-{index}")) + 1)
                )
            )

    errors = run_threads(8, work)
    assert errors == []
    assert [get(db, f"mesa-{i}") for i in range(8)] == ["25"] * 8


def _value(session, key):
    found = session.execute(text("SELECT value FROM settings WHERE key = :k"), {"k": key}).scalar()
    return found or "0"


def test_read_then_write_on_the_same_row_loses_no_update(db):
    # Regressão do BUSY_SNAPSHOT: com BEGIN adiado, ler e depois escrever com outro escritor no meio falha
    # na hora; com BEGIN IMMEDIATE os escritores se enfileiram e nenhuma soma se perde.
    def work(_index):
        for _ in range(20):
            db.write(lambda s: put(s, "contador", str(int(_value(s, "contador")) + 1)))

    errors = run_threads(8, work)
    assert errors == []
    assert get(db, "contador") == "160"


def test_reader_is_not_blocked_by_a_long_writer(db):
    db.write(lambda s: put(s, "a", "antes"))
    started, release = threading.Event(), threading.Event()

    def slow_writer():
        def work(session):
            put(session, "a", "depois")
            started.set()
            release.wait(5)

        db.write(work)

    thread = threading.Thread(target=slow_writer)
    thread.start()
    assert started.wait(5)
    begin = time.monotonic()
    assert get(db, "a") == "antes"  # WAL: o leitor vê o que estava confirmado e não espera
    assert time.monotonic() - begin < 1
    release.set()
    thread.join(5)
    assert get(db, "a") == "depois"


def test_external_writer_holding_the_lock_becomes_busy_not_a_hang(tmp_path):
    folder = prepare_data_dir(tmp_path / "d")
    database = Database(folder / DB_NAME, busy_timeout_ms=100, retry_delays=(0.01,))
    migrate(database)
    outsider = sqlite3.connect(folder / DB_NAME, isolation_level=None)
    outsider.execute("BEGIN IMMEDIATE")
    begin = time.monotonic()
    with pytest.raises(StorageBusy) as caught:
        database.write(lambda s: put(s, "x", "1"))
    assert time.monotonic() - begin < 5
    assert caught.value.status == 503
    assert caught.value.retry_after == 1
    outsider.execute("ROLLBACK")
    outsider.close()
    database.write(lambda s: put(s, "x", "1"))  # solto o lock, volta a escrever
    assert get(database, "x") == "1"
    database.close()


def locked():
    return OperationalError("INSERT", {}, sqlite3.OperationalError("database is locked"))


def test_busy_is_retried_a_few_times_then_succeeds(tmp_path):
    database = Database(prepare_data_dir(tmp_path / "d") / DB_NAME, retry_delays=(0, 0, 0))
    migrate(database)
    attempts = []

    def work(session):
        attempts.append(1)
        if len(attempts) < 3:
            raise locked()
        put(session, "k", "v")

    database.write(work)
    assert len(attempts) == 3
    assert get(database, "k") == "v"
    database.close()


def test_busy_that_never_clears_is_service_unavailable(tmp_path):
    database = Database(prepare_data_dir(tmp_path / "d") / DB_NAME, retry_delays=(0, 0, 0))
    attempts = []

    def work(_session):
        attempts.append(1)
        raise locked()

    with pytest.raises(StorageBusy):
        database.write(work)
    assert len(attempts) == 4  # a primeira e três novas
    database.close()


def test_other_database_errors_are_not_retried_nor_hidden(db):
    attempts = []

    def work(session):
        attempts.append(1)
        session.execute(text("SELECT * FROM tabela_que_nao_existe"))

    with pytest.raises(OperationalError):
        db.write(work)
    assert attempts == [1]


def test_failed_write_rolls_back(db):
    def work(session):
        put(session, "k", "meio")
        raise ValueError("falhou no meio")

    with pytest.raises(ValueError, match="meio"):
        db.write(work)
    assert get(db, "k") is None


def test_exhausted_pool_is_busy_not_a_hang(tmp_path):
    database = Database(
        prepare_data_dir(tmp_path / "d") / DB_NAME, pool_size=1, max_overflow=0, pool_timeout=0.2
    )
    migrate(database)
    inside, release = threading.Event(), threading.Event()

    def hold(session):
        session.execute(text("SELECT 1"))  # a conexão só é tomada do pool no primeiro uso
        inside.set()
        release.wait(5)

    thread = threading.Thread(target=lambda: database.read(hold))
    thread.start()
    assert inside.wait(5)
    with pytest.raises(StorageBusy):
        database.read(lambda s: s.execute(text("SELECT 1")))
    release.set()
    thread.join(5)
    assert database.read(lambda s: s.execute(text("SELECT 1")).scalar()) == 1
    database.close()


def test_backup_is_consistent_private_and_has_the_data(db, tmp_path):
    db.write(lambda s: put(s, "k", "v"))  # ainda pode estar só no WAL
    target = tmp_path / "copia.db"
    db.backup_to(target)
    copy = sqlite3.connect(target)
    assert copy.execute("SELECT value FROM settings WHERE key = 'k'").fetchone() == ("v",)
    copy.close()
    if os.name == "posix":
        assert mode(target) == 0o600
