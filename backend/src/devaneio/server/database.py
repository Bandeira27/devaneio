"""O banco SQLite do servidor: arquivo protegido, conexões seguras entre threads e transações curtas.

Premissa (``docs/desenho-banco.md``): **um banco, um processo de servidor**. Isso é imposto por um
``flock`` na pasta de dados. O SQLite tem um escritor por vez no arquivo inteiro: o WAL deixa leitores e
esse escritor andarem juntos, mas não cria vários escritores. Por isso:

- cada operação abre a **sua** ``Session`` e a fecha, nunca guardada nem passada a outra thread;
- escrita começa com ``BEGIN IMMEDIATE``: pega o direito de escrever já no começo, em vez de tentar subir
  de leitor a escritor no meio (o que dá ``SQLITE_BUSY`` na hora, sem esperar o ``busy_timeout``);
- ``BUSY``/``LOCKED`` tem espera, poucas novas tentativas e, esgotadas, vira ``StorageBusy`` (HTTP 503);
- a unidade de trabalho de ``read``/``write`` só mexe no banco: nada de LLM nem de rede dentro dela.

O que é específico do SQLite (``PRAGMA``, ``BEGIN IMMEDIATE``, WAL, ``flock``) fica neste módulo.
"""

from __future__ import annotations

import importlib
import os
import sqlite3
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from typing import IO, TypeVar

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from .errors import ApiFailure, DatabaseError
from .files import FILE_MODE, create_private_file, tighten

# Só Unix tem ``flock``; no Windows a premissa de um processo só fica documentada.
fcntl: ModuleType | None = importlib.import_module("fcntl") if os.name == "posix" else None

T = TypeVar("T")

DB_NAME = "devaneio.db"
LOCK_NAME = "devaneio.lock"
BUSY_TIMEOUT_MS = 5000
RETRY_DELAYS = (0.05, 0.1, 0.2)  # espera entre as novas tentativas, além do busy_timeout
SQLITE_BUSY = 5
SQLITE_LOCKED = 6
MODE_OPTION = "devaneio_mode"  # opção de execução: "write" abre a transação com BEGIN IMMEDIATE


class StorageBusy(ApiFailure):
    """O banco seguiu ocupado depois da espera e das novas tentativas: o cliente tenta de novo logo."""

    def __init__(self) -> None:
        super().__init__(
            503, "busy", "o servidor está ocupado, tente de novo em instantes", retry_after=1
        )


def acquire_instance_lock(data_dir: Path) -> IO[bytes] | None:
    """Trava a pasta de dados para este processo (não bloqueia); ``None`` onde não há ``flock``.

    O arquivo devolvido precisa ficar aberto enquanto o servidor viver: fechar solta a trava.
    """
    if fcntl is None:  # pragma: no cover - sem fcntl
        return None
    try:
        descriptor = os.open(data_dir / LOCK_NAME, os.O_WRONLY | os.O_CREAT, FILE_MODE)
    except OSError as exc:
        raise DatabaseError(f"não consegui criar {LOCK_NAME}: {exc.strerror}") from exc
    handle = os.fdopen(descriptor, "ab")  # fica aberto de propósito: é a trava
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        raise DatabaseError(
            "outro servidor do Devaneio já usa esta pasta de dados: um banco, um servidor"
        ) from None
    return handle


class Database:
    """O arquivo SQLite aberto: ``read``/``write`` rodam uma unidade de trabalho numa ``Session`` própria."""

    def __init__(
        self,
        path: Path,
        *,
        busy_timeout_ms: int = BUSY_TIMEOUT_MS,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_timeout: float = 10.0,
        retry_delays: tuple[float, ...] = RETRY_DELAYS,
    ) -> None:
        self.path = Path(path).resolve()
        self._retry_delays = retry_delays
        create_private_file(self.path)
        tighten(self.path, "o banco")
        self.engine = create_engine(
            f"sqlite:///{self.path}",
            poolclass=QueuePool,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            connect_args={"check_same_thread": False},
        )
        _install_events(self.engine, busy_timeout_ms)
        self._reader = sessionmaker(self.engine, expire_on_commit=False)
        self._writer = sessionmaker(
            self.engine.execution_options(**{MODE_OPTION: "write"}), expire_on_commit=False
        )
        try:
            with (
                self.engine.connect() as connection
            ):  # liga o WAL e cria -wal/-shm já com o modo certo
                connection.exec_driver_sql("SELECT 1")
            for suffix in ("-wal", "-shm"):
                side = Path(f"{self.path}{suffix}")
                if side.exists():
                    tighten(side, f"o arquivo {suffix[1:]} do banco")
        except BaseException:
            self.engine.dispose()  # abriu pela metade: não deixa conexão para trás
            raise

    def read(self, work: Callable[[Session], T]) -> T:
        """Roda ``work`` numa transação de leitura (só ``SELECT``); sem escrita aqui dentro."""
        try:
            with self._reader.begin() as session:
                return work(session)
        except PoolTimeoutError:
            raise StorageBusy() from None
        except OperationalError as exc:
            failure = _classify(exc)
            if failure is exc:
                raise
            raise failure from exc

    def write(self, work: Callable[[Session], T]) -> T:
        """Roda ``work`` numa transação de escrita (``BEGIN IMMEDIATE``), com novas tentativas se ocupado.

        ``work`` pode rodar mais de uma vez: só mexe no banco e relê o que precisa dentro dele.
        """
        for attempt in range(len(self._retry_delays) + 1):
            try:
                with self._writer.begin() as session:
                    return work(session)
            except PoolTimeoutError:
                raise StorageBusy() from None
            except OperationalError as exc:
                failure = _classify(exc)
                if not isinstance(failure, StorageBusy):
                    raise
                if attempt == len(self._retry_delays):
                    raise failure from exc
                time.sleep(self._retry_delays[attempt])
        raise AssertionError("inalcançável")  # pragma: no cover

    @contextmanager
    def raw_connection(self) -> Iterator[sqlite3.Connection]:
        """A conexão ``sqlite3`` por baixo, para a API de backup do SQLite."""
        connection = self.engine.raw_connection()
        try:
            driver = connection.driver_connection
            if not isinstance(driver, sqlite3.Connection):
                raise DatabaseError("o driver do banco não é o sqlite3")
            yield driver
        finally:
            connection.close()

    def backup_to(self, target: Path, *, exclusive: bool = False) -> None:
        """Cópia consistente do banco inteiro (inclui o que ainda está no WAL), arquivo ``0600``.

        Não leva a chave do LLM nem nada fora do banco. Com ``exclusive``, um destino que já existe é
        ``FileExistsError`` (a criação é atômica, sem janela entre checar e criar), e uma cópia que falha no meio
        não deixa um arquivo pela metade para trás.
        """
        target = Path(target)
        create_private_file(target, exclusive=exclusive)
        tighten(target, "a cópia")
        destination = sqlite3.connect(target)
        try:
            with self.raw_connection() as source:
                source.backup(destination)
        except BaseException:
            destination.close()
            if exclusive:
                target.unlink(missing_ok=True)
            raise
        destination.close()

    def close(self) -> None:
        """Fecha as conexões do pool."""
        self.engine.dispose()


def _classify(exc: OperationalError) -> Exception:
    """``StorageBusy`` se o SQLite recusou por estar ocupado ou travado; senão, o erro como veio."""
    original = exc.orig
    code = getattr(original, "sqlite_errorcode", None)  # Python 3.11+
    if isinstance(code, int):
        busy = code & 0xFF in (SQLITE_BUSY, SQLITE_LOCKED)
    else:
        busy = "locked" in str(original).lower() or "busy" in str(original).lower()
    return StorageBusy() if busy else exc


def _install_events(engine: Engine, busy_timeout_ms: int) -> None:
    """Liga o controle explícito de transação e os ``PRAGMA`` de toda conexão nova.

    É a receita do SQLAlchemy para o ``pysqlite``: o driver não emite ``BEGIN`` sozinho, e quem emite é o
    evento ``begin``, aqui ``BEGIN IMMEDIATE`` para escrita.
    """

    @event.listens_for(engine, "connect")
    def on_connect(dbapi_connection: sqlite3.Connection, _record: object) -> None:
        dbapi_connection.isolation_level = None
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute(
            "PRAGMA synchronous=NORMAL"
        )  # com WAL: queda do SO perde a última, não corrompe
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
        cursor.close()

    @event.listens_for(engine, "begin")
    def on_begin(connection: Connection) -> None:
        if connection.get_execution_options().get(MODE_OPTION) == "write":
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        else:
            connection.exec_driver_sql("BEGIN")
