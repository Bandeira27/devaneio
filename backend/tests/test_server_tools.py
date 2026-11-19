"""``devaneio exportar`` e ``devaneio backup``: uma mesa para fora no formato do CLI e uma cópia consistente do banco."""

import os
import sqlite3
import stat

import pytest

from conftest import CAMPAIGN_PATH, make_storage
from devaneio.game import load_game
from devaneio.server import Catalog, TableService
from devaneio.server.__main__ import main
from devaneio.server.cli_tools import backup_main, export_main, import_main
from devaneio.server.database import DB_NAME, Database, acquire_instance_lock
from devaneio.server.files import prepare_data_dir
from devaneio.server.models import CommandRequest, CreateTableRequest, JoinRequest
from devaneio.server.records import TableRecords
from devaneio.server.settings_store import KEY_FILE
from devaneio.server.storage import Storage

KEY = "sk-CANARIO-backup-1234"
posix_only = pytest.mark.skipif(os.name != "posix", reason="modos POSIX")


@pytest.fixture
def world(tmp_path):
    """Um servidor com uma mesa jogada de verdade (dois jogadores, eventos) no banco de ``tmp_path/dados``, já parado."""
    catalog = Catalog(CAMPAIGN_PATH.parent)
    storage = make_storage(tmp_path / "dados", max_tables=10)
    service = TableService(catalog, storage, invite_source=lambda: "convite")
    created = service.create_table(
        CreateTableRequest(campaign_id="sombra-do-vale", host_name="Ana", seed=7)
    )
    joined = service.join_table(created.table_id, JoinRequest(name="Bia", invite_code="convite"))
    for token, line in (
        (created.host_token, 'entrar ana "Ana"'),
        (joined.token, 'entrar bia "Bia"'),
    ):
        revision = service.get_table(created.table_id, token).revision
        service.run_command(created.table_id, token, CommandRequest(line=line, revision=revision))
    session = service.load_session(created.table_id)
    storage._db.close()  # o servidor parou: o banco fica livre para as ferramentas
    return tmp_path, created.table_id, session


def folders(tmp_path):
    return ["--campanhas", str(CAMPAIGN_PATH.parent), "--dados", str(tmp_path / "dados")]


# --- exportar -----------------------------------------------------------------------------


def test_the_export_is_a_solo_save_the_terminal_game_opens(world, capsys):
    tmp_path, table_id, _ = world
    out = tmp_path / "saida" / "partida.json"
    out.parent.mkdir()
    assert export_main([table_id, "--saida", str(out), *folders(tmp_path)]) == 0
    assert "exportada" in capsys.readouterr().out
    session = load_game(out)  # o jogo no terminal abre
    assert session.table is None  # sem jogadores, hashes de token nem de convite
    assert session.state.events
    text = out.read_text(encoding="utf-8")
    for leaked in ("token_hash", "invite_hash", "convite"):
        assert leaked not in text


def test_the_export_with_the_table_goes_back_to_another_database_with_the_same_tokens(
    world, tmp_path_factory, capsys
):
    tmp_path, table_id, original = world
    out = tmp_path / f"{table_id}.json"  # o importador reconhece a mesa pelo nome do arquivo
    assert export_main([table_id, "--saida", str(out), "--com-mesa", *folders(tmp_path)]) == 0
    other = tmp_path_factory.mktemp("outro")
    args = ["--campanhas", str(CAMPAIGN_PATH.parent), "--dados", str(other)]
    assert import_main([str(out), *args]) == 0
    capsys.readouterr()
    restored = TableRecords(make_storage(other, max_tables=5), Catalog(CAMPAIGN_PATH.parent)).load(
        table_id
    )
    assert restored.state == original.state
    assert restored.table == original.table  # jogadores, hashes de token e de convite, fase


@posix_only
def test_the_exported_file_is_private_and_never_overwrites(world, capsys):
    tmp_path, table_id, _ = world
    out = tmp_path / "partida.json"
    assert export_main([table_id, "--saida", str(out), *folders(tmp_path)]) == 0
    assert stat.S_IMODE(out.stat().st_mode) == 0o600
    before = out.read_bytes()
    assert export_main([table_id, "--saida", str(out), *folders(tmp_path)]) == 1
    assert "já existe" in capsys.readouterr().err
    assert out.read_bytes() == before


def test_an_archived_table_can_be_exported_too(world, capsys):
    tmp_path, table_id, _ = world
    storage = make_storage(tmp_path / "dados", max_tables=10)
    storage.archive(table_id)
    storage._db.close()
    out = tmp_path / "arquivada.json"
    assert export_main([table_id, "--saida", str(out), *folders(tmp_path)]) == 0
    assert load_game(out).state.events


def test_exporting_an_unknown_table_is_an_error_and_writes_nothing(world, capsys):
    tmp_path, _, _ = world
    out = tmp_path / "nada.json"
    assert export_main(["0123456789abcdef", "--saida", str(out), *folders(tmp_path)]) == 1
    assert "mesa não encontrada" in capsys.readouterr().err
    assert not out.exists()


@pytest.mark.parametrize("table_id", ["../x", "ABC", "0123456789abcdef\n", ""])
def test_a_malformed_id_is_refused_before_any_path_is_built(world, capsys, table_id, monkeypatch):
    tmp_path, _, _ = world
    monkeypatch.chdir(tmp_path)
    assert export_main([table_id, *folders(tmp_path)]) == 1
    assert "o id da mesa" in capsys.readouterr().err
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "dados"
    ]  # nada foi criado, nem fora da pasta


def test_exporting_does_not_create_a_database_where_there_is_none(tmp_path, capsys):
    empty = tmp_path / "vazio"
    assert export_main(["0123456789abcdef", *folders_of(tmp_path, empty)]) == 1
    assert "não há banco" in capsys.readouterr().err
    assert not empty.exists()


def folders_of(tmp_path, data):
    return ["--campanhas", str(CAMPAIGN_PATH.parent), "--dados", str(data)]


def test_the_tools_are_reached_through_main(world, capsys):
    tmp_path, table_id, _ = world
    out = tmp_path / "pelo-main.json"
    assert main(["exportar", table_id, "--saida", str(out), *folders(tmp_path)]) == 0
    assert out.exists()


def test_an_export_cannot_run_while_the_server_holds_the_database(world, capsys):
    tmp_path, table_id, _ = world
    held = acquire_instance_lock(tmp_path / "dados")
    try:
        assert export_main([table_id, "--saida", str(tmp_path / "x.json"), *folders(tmp_path)]) == 1
    finally:
        held.close()
    assert "um banco, um servidor" in capsys.readouterr().err


# --- backup -------------------------------------------------------------------------------


def test_the_backup_is_a_consistent_copy_with_every_table_and_no_key(world, capsys):
    tmp_path, table_id, _ = world
    (tmp_path / "dados" / KEY_FILE).write_text(KEY + "\n", encoding="utf-8")
    storage = make_storage(tmp_path / "dados", max_tables=10)
    storage.archive(table_id)  # arquivadas também vão na cópia
    storage._db.close()
    destination = tmp_path / "copia.db"
    assert backup_main([str(destination), "--dados", str(tmp_path / "dados")]) == 0
    assert "sem a chave" in capsys.readouterr().out
    copy = sqlite3.connect(destination)
    assert copy.execute("SELECT count(*) FROM tables").fetchone() == (1,)
    assert copy.execute("SELECT archived_at IS NOT NULL FROM tables").fetchone() == (1,)
    copy.close()
    assert KEY.encode() not in destination.read_bytes()
    opened = Database(destination)  # abre como um banco do Devaneio
    assert make_storage_from(opened).exists(table_id, scope="archived")
    opened.close()


def make_storage_from(database):
    return Storage(database, max_tables=5)


@posix_only
def test_the_backup_is_private(world):
    tmp_path, _, _ = world
    destination = tmp_path / "copia.db"
    assert backup_main([str(destination), "--dados", str(tmp_path / "dados")]) == 0
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600


def test_the_backup_refuses_an_existing_destination_and_a_missing_database(
    world, capsys, tmp_path_factory
):
    tmp_path, _, _ = world
    existing = tmp_path / "ja-existe.db"
    existing.write_bytes(b"importante")
    assert backup_main([str(existing), "--dados", str(tmp_path / "dados")]) == 1
    assert "já existe" in capsys.readouterr().err
    assert existing.read_bytes() == b"importante"  # nada foi sobrescrito
    empty = tmp_path_factory.mktemp("vazio")
    assert backup_main([str(tmp_path / "x.db"), "--dados", str(empty)]) == 1
    assert "não há banco" in capsys.readouterr().err
    assert not (empty / DB_NAME).exists()  # não criou um banco para copiar


def test_the_backup_never_overwrites_a_file_that_appears_after_the_check(
    world, capsys, monkeypatch
):
    tmp_path, _, _ = world
    destination = tmp_path / "copia.db"
    real = Database.backup_to

    def late(self, target, *, exclusive=False):
        destination.write_bytes(
            b"chegou depois da checagem"
        )  # outro processo criou o arquivo na janela
        return real(self, target, exclusive=exclusive)

    monkeypatch.setattr(Database, "backup_to", late)
    assert backup_main([str(destination), "--dados", str(tmp_path / "dados")]) == 1
    assert "já existe" in capsys.readouterr().err
    assert destination.read_bytes() == b"chegou depois da checagem"


@pytest.mark.parametrize("suffix", ["", "-wal", "-shm"])
def test_the_backup_cannot_target_the_database_own_files(world, capsys, suffix):
    tmp_path, _, _ = world
    target = tmp_path / "dados" / f"{DB_NAME}{suffix}"
    before = target.read_bytes() if target.exists() else None
    assert backup_main([str(target), "--dados", str(tmp_path / "dados")]) == 1
    assert "próprio banco" in capsys.readouterr().err
    assert (target.read_bytes() if target.exists() else None) == before


def test_a_backup_that_fails_halfway_leaves_no_partial_file_behind(world, capsys, monkeypatch):
    tmp_path, _, _ = world
    destination = tmp_path / "copia.db"

    def broken(self):
        raise sqlite3.OperationalError("disco cheio")

    monkeypatch.setattr(Database, "raw_connection", broken)
    assert backup_main([str(destination), "--dados", str(tmp_path / "dados")]) == 1
    assert "disco cheio" in capsys.readouterr().err
    assert not destination.exists()  # e uma nova tentativa não esbarra num arquivo pela metade


def test_the_backup_does_not_migrate_the_database(tmp_path, capsys):
    folder = prepare_data_dir(tmp_path / "dados")
    raw = sqlite3.connect(folder / DB_NAME)
    raw.execute("CREATE TABLE settings (key TEXT NOT NULL PRIMARY KEY, value TEXT NOT NULL)")
    raw.execute("PRAGMA user_version = 1")
    raw.commit()
    raw.close()
    destination = tmp_path / "copia.db"
    assert backup_main([str(destination), "--dados", str(folder)]) == 0
    copy = sqlite3.connect(destination)
    assert copy.execute("PRAGMA user_version").fetchone() == (
        1,
    )  # cópia fiel, sem mexer no esquema
    copy.close()


def test_the_backup_cannot_run_while_the_server_holds_the_database(world, capsys):
    tmp_path, _, _ = world
    held = acquire_instance_lock(tmp_path / "dados")
    try:
        assert backup_main([str(tmp_path / "copia.db"), "--dados", str(tmp_path / "dados")]) == 1
    finally:
        held.close()
    assert "um banco, um servidor" in capsys.readouterr().err
    assert not (tmp_path / "copia.db").exists()
