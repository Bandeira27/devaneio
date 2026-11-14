"""Onde as mesas vivem em disco e como o acesso a cada uma é serializado.

O id da mesa é gerado aqui e validado de novo quando vem da URL: só o formato que o
próprio servidor produz vira caminho, e sempre dentro da pasta de dados."""

from __future__ import annotations

import re
import secrets
import threading
from pathlib import Path

TABLE_ID = re.compile(r"^[a-f0-9]{16}$")


class Storage:
    def __init__(self, data_dir: Path, *, max_tables: int) -> None:
        self.data_dir = Path(data_dir).resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.max_tables = max_tables
        self._locks: dict[str, threading.Lock] = {}
        self._registry = threading.Lock()

    def path_for(self, table_id: str) -> Path | None:
        """Caminho da mesa, ou ``None`` se o id não tem o formato gerado aqui, resolve para
        fora da pasta de dados ou não existe."""
        if not TABLE_ID.match(table_id):
            return None
        path = (self.data_dir / f"{table_id}.json").resolve()
        if not path.is_relative_to(self.data_dir) or not path.is_file():
            return None
        return path

    def new_table_path(self) -> tuple[str, Path]:
        while True:
            table_id = secrets.token_hex(8)
            path = self.data_dir / f"{table_id}.json"
            if not path.exists():
                return table_id, path

    def count(self) -> int:
        return sum(1 for p in self.data_dir.glob("*.json") if TABLE_ID.match(p.stem))

    def lock(self, table_id: str) -> threading.Lock:
        """Um lock por mesa existente; o dicionário não cresce com ids inventados porque
        quem chama já validou o id com ``path_for``."""
        with self._registry:
            return self._locks.setdefault(table_id, threading.Lock())
