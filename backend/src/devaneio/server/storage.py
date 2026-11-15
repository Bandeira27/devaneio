"""Onde as mesas vivem em disco e como o acesso a cada uma é serializado.

O id da mesa é gerado aqui e validado de novo quando vem da URL: só o formato que o
próprio servidor produz vira caminho, e sempre dentro da pasta de dados. O arquivo é a fonte
única da verdade; em memória ficam só a coordenação (lock, versão, vagas) e os parágrafos de
narração do LLM, que são exibição e somem ao reiniciar."""

from __future__ import annotations

import re
import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .models import Flavor

TABLE_ID = re.compile(r"^[a-f0-9]{16}$")
MAX_WAITERS = 16  # esperas de long-poll simultâneas por mesa; acima disso, responde de imediato
MAX_NARRATIONS = 200  # narrações e falas guardadas por mesa; as mais antigas saem primeiro


@dataclass
class _Table:
    lock: threading.Lock = field(default_factory=threading.Lock)
    version: int = 0  # sobe a cada gravação; quem espera compara com a que viu
    waiters: int = 0
    saying: bool = False  # uma chamada de texto livre ao LLM por vez por mesa
    flavors: dict[int, Flavor] = field(default_factory=dict)  # por índice de evento
    last_say: dict[str, float] = field(default_factory=dict)  # por jogador, no relógio da mesa
    changed: threading.Condition = field(init=False)

    def __post_init__(self) -> None:
        self.changed = threading.Condition(self.lock)  # a mesma trava dos comandos


class Storage:
    def __init__(
        self,
        data_dir: Path,
        *,
        max_tables: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._clock = clock  # injetável: os testes do intervalo do texto livre não esperam
        self.data_dir = Path(data_dir).resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.max_tables = max_tables
        self._tables: dict[str, _Table] = {}
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

    def _table(self, table_id: str) -> _Table:
        """Uma entrada por mesa existente; o dicionário não cresce com ids inventados porque
        quem chama já validou o id com ``path_for``."""
        with self._registry:
            return self._tables.setdefault(table_id, _Table())

    def lock(self, table_id: str) -> threading.Lock:
        return self._table(table_id).lock

    def condition(self, table_id: str) -> threading.Condition:
        """Condição sobre o lock da mesa: ``wait`` solta o lock, então comandos seguem."""
        return self._table(table_id).changed

    def version(self, table_id: str) -> int:
        return self._table(table_id).version

    def announce_change(self, table_id: str) -> None:
        """Avisa quem espera que a mesa foi gravada. Chamar com o lock da mesa tomado."""
        table = self._table(table_id)
        table.version += 1
        table.changed.notify_all()

    def enter_say(self, table_id: str) -> bool:
        """Reserva a única chamada de texto livre da mesa; ``False`` se já há uma em curso
        (cada uma custa chamadas ao LLM de quem roda o servidor)."""
        table = self._table(table_id)
        with self._registry:
            if table.saying:
                return False
            table.saying = True
            return True

    def leave_say(self, table_id: str) -> None:
        table = self._table(table_id)
        with self._registry:
            table.saying = False

    def flavors(self, table_id: str) -> dict[int, Flavor]:
        """Narração e fala do LLM por índice de evento (só em memória: nunca vão ao arquivo, e
        depois de reiniciar o servidor os eventos antigos voltam só com a gramática)."""
        table = self._table(table_id)
        with self._registry:
            return dict(table.flavors)

    def store_flavors(self, table_id: str, flavors: dict[int, Flavor]) -> None:
        table = self._table(table_id)
        with self._registry:
            table.flavors.update(flavors)
            while len(table.flavors) > MAX_NARRATIONS:
                del table.flavors[next(iter(table.flavors))]  # o dict guarda a ordem de inserção

    def say_cooldown_left(self, table_id: str, player_id: str, cooldown: float) -> float:
        """Segundos até o jogador poder pedir outro texto livre (0 se já pode). Cada pedido
        custa chamadas ao LLM de quem roda o servidor: o intervalo vale por jogador."""
        table = self._table(table_id)
        with self._registry:
            last = table.last_say.get(player_id)
            if last is None:
                return 0.0
            return max(0.0, cooldown - (self._clock() - last))

    def mark_say(self, table_id: str, player_id: str) -> None:
        table = self._table(table_id)
        with self._registry:
            table.last_say[player_id] = self._clock()

    def enter_wait(self, table_id: str) -> bool:
        """Reserva uma vaga de espera; ``False`` se a mesa já tem ``MAX_WAITERS``."""
        table = self._table(table_id)
        with self._registry:
            if table.waiters >= MAX_WAITERS:
                return False
            table.waiters += 1
            return True

    def leave_wait(self, table_id: str) -> None:
        table = self._table(table_id)
        with self._registry:
            table.waiters -= 1
