"""Migrações: ordem, uma transação por migração, recusas e a ausência de deriva em relação ao ORM."""

import sqlite3
import stat

import pytest
from sqlalchemy import inspect, text

from devaneio.server import migrations
from devaneio.server.database import DB_NAME, Database
from devaneio.server.errors import DatabaseError
from devaneio.server.files import prepare_data_dir
from devaneio.server.migrations import LATEST, migrate, schema_version
from devaneio.server.orm import Base


@pytest.fixture
def folder(tmp_path):
    return prepare_data_dir(tmp_path / "d")


def test_new_database_goes_to_the_latest_version(folder):
    db = Database(folder / DB_NAME)
    assert schema_version(db) == 0
    assert migrate(db) == LATEST
    assert schema_version(db) == LATEST
    db.close()


def test_migrating_twice_changes_nothing_and_makes_no_backup(folder):
    db = Database(folder / DB_NAME)
    migrate(db)
    assert migrate(db) == LATEST
    assert list(folder.glob("*.bak")) == []
    db.close()


def test_database_from_a_newer_version_is_refused(folder):
    db = Database(folder / DB_NAME)
    migrate(db)
    db.write(lambda s: s.execute(text(f"PRAGMA user_version = {LATEST + 5}")))
    with pytest.raises(DatabaseError, match="mais nova"):
        migrate(db)
    db.close()


def test_a_file_with_foreign_tables_is_refused(folder):
    raw = sqlite3.connect(folder / DB_NAME)
    raw.execute("CREATE TABLE outra_coisa (x)")
    raw.commit()
    raw.close()
    db = Database(folder / DB_NAME)
    with pytest.raises(DatabaseError, match="não é um banco do Devaneio"):
        migrate(db)
    db.close()


def test_failure_in_the_middle_rolls_back_ddl_and_version(folder, monkeypatch):
    db = Database(folder / DB_NAME)
    migrate(db)
    broken = (
        *migrations.MIGRATIONS,
        ("CREATE TABLE nova (x INTEGER)", "INSERT INTO tabela_inexistente VALUES (1)"),
    )
    monkeypatch.setattr(migrations, "MIGRATIONS", broken)
    monkeypatch.setattr(migrations, "LATEST", len(broken))
    with pytest.raises(Exception, match="tabela_inexistente"):
        migrate(db)
    assert schema_version(db) == LATEST  # a versão não avançou
    tables = db.read(lambda s: inspect(s.connection()).get_table_names())
    assert "nova" not in tables  # nem o DDL que rodou antes do erro
    db.close()


def test_pending_migration_runs_once_and_leaves_a_private_backup(folder, monkeypatch):
    db = Database(folder / DB_NAME)
    migrate(db)
    db.write(lambda s: s.execute(text("INSERT INTO settings VALUES ('k', 'v')")))
    extended = (*migrations.MIGRATIONS, ("CREATE TABLE nova (x INTEGER)",))
    monkeypatch.setattr(migrations, "MIGRATIONS", extended)
    monkeypatch.setattr(migrations, "LATEST", len(extended))
    assert migrate(db) == len(extended)
    assert migrate(db) == len(extended)  # sem repetir
    backup = folder / f"{DB_NAME}.pre-v{LATEST}.bak"
    assert backup.exists()
    copy = sqlite3.connect(backup)
    assert copy.execute("SELECT value FROM settings WHERE key = 'k'").fetchone() == ("v",)
    assert copy.execute("SELECT name FROM sqlite_master WHERE name = 'nova'").fetchone() is None
    copy.close()
    assert stat.S_IMODE(backup.stat().st_mode) == 0o600
    db.close()


def test_migrated_schema_matches_the_orm_models(folder):
    db = Database(folder / DB_NAME)
    migrate(db)

    def read(session):
        inspector = inspect(session.connection())
        return {
            name: {
                column["name"]: (column["nullable"], bool(column["primary_key"]))
                for column in inspector.get_columns(name)
            }
            for name in inspector.get_table_names()
        }

    actual = db.read(read)
    expected = {
        table.name: {
            column.name: (column.nullable, bool(column.primary_key)) for column in table.columns
        }
        for table in Base.metadata.tables.values()
    }
    assert actual == expected
    db.close()
