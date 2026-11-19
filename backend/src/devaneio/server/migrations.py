"""Migrações do banco, numeradas e em ordem, versionadas por ``PRAGMA user_version``.

Cada migração é SQL explícito (``create_all`` derivaria dos modelos de hoje e deixaria de reproduzir o
passado) e roda **inteira numa só transação** ``BEGIN IMMEDIATE``, junto com o novo ``user_version``: se
algo falha no meio, DDL e versão voltam juntos e a próxima subida tenta de novo. Só roda o que a versão
atual ainda não tem. Antes de migrar um banco que já tem dados, sai uma cópia consistente ao lado.

Alembic só entra com justificativa (``docs/desenho-banco.md``, "Quando adotar Alembic").
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from .database import Database
from .errors import DatabaseError

# A posição na lista é a versão: a primeira leva o banco de 0 a 1. Nunca editar uma já publicada.
MIGRATIONS: tuple[tuple[str, ...], ...] = (
    (
        """
        CREATE TABLE settings (
            key TEXT NOT NULL PRIMARY KEY,
            value TEXT NOT NULL
        )
        """,
    ),
)
LATEST = len(MIGRATIONS)


def schema_version(db: Database) -> int:
    """A versão do esquema gravada no arquivo (0 = banco novo)."""

    def read(session: Session) -> int:
        return int(session.execute(text("PRAGMA user_version")).scalar_one())

    return db.read(read)


def migrate(db: Database) -> int:
    """Leva o banco à última versão e devolve a versão final.

    ``DatabaseError`` se o arquivo é de uma versão mais nova que este código, ou se tem tabelas mas
    nenhuma versão (não é um banco do Devaneio).
    """
    current = schema_version(db)
    if current > LATEST:
        raise DatabaseError(
            f"o banco é de uma versão mais nova (esquema {current}; este servidor entende até {LATEST})"
        )
    if current == 0 and _has_tables(db):
        raise DatabaseError("o arquivo do banco tem tabelas, mas não é um banco do Devaneio")
    if current == LATEST:
        return current
    if current > 0:
        db.backup_to(db.path.with_name(f"{db.path.name}.pre-v{current}.bak"))
    for version in range(current + 1, LATEST + 1):
        statements = MIGRATIONS[version - 1]

        def apply(
            session: Session, statements: tuple[str, ...] = statements, version: int = version
        ) -> None:
            for statement in statements:
                session.execute(text(statement))
            session.execute(text(f"PRAGMA user_version = {int(version)}"))

        db.write(apply)
    return LATEST


def _has_tables(db: Database) -> bool:
    def count(session: Session) -> int:
        return int(
            session.execute(
                text("SELECT count(*) FROM sqlite_master WHERE type = 'table'")
            ).scalar_one()
        )

    return db.read(count) > 0
