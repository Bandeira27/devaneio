"""Onde as mesas vivem (no banco) e como o acesso a cada uma é serializado.

O id da mesa é gerado aqui e validado de novo quando vem da URL: só o formato que o próprio servidor produz
chega ao banco. O banco é a fonte única da verdade; em memória ficam só a coordenação (lock, versão, vagas,
intervalo do texto livre) e, por mesa, a ``Presentation`` (narração e mural do LLM), que some ao reiniciar.

Toda gravação de uma mesa acontece sob o lock dela: ler, mudar e gravar sem outro no meio. Cada leitura e cada
gravação é uma transação curta no banco (``Database.read``/``write``); nenhuma atravessa chamada ao LLM.
"""

from __future__ import annotations

import re
import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import ColumnElement, delete, func, select, true, update
from sqlalchemy.orm import Session

from .database import Database
from .errors import ApiFailure
from .orm import GameTable
from .presentation import Presentation

TABLE_ID = re.compile(r"[a-f0-9]{16}\Z")  # \Z, não $: o $ aceitaria uma quebra de linha no fim
MAX_WAITERS = 16  # esperas de long-poll simultâneas por mesa; acima disso, responde de imediato


@dataclass(frozen=True)
class Record:
    """O que se guarda de uma mesa: textos JSON já prontos, e onde a campanha dela está (relativo à pasta de campanhas)."""

    campaign_path: str
    state: str
    meta: str
    content: str | None


@dataclass(frozen=True)
class Summary:
    """Uma linha da lista de mesas: o id, a ``TableMeta`` em JSON, a última gravação e, se arquivada, quando."""

    table_id: str
    meta: str
    updated_at: float
    archived_at: float | None


Scope = Literal["active", "archived", "any"]


def _in(scope: Scope) -> ColumnElement[bool]:
    """O filtro de uma consulta: só as mesas ativas, só as arquivadas ou todas."""
    if scope == "active":
        return GameTable.archived_at.is_(None)
    if scope == "archived":
        return GameTable.archived_at.is_not(None)
    return true()


def _active_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(GameTable).where(_in("active"))) or 0


@dataclass
class _Slot:
    busy: bool = False  # uma chamada ao LLM desse tipo por vez por mesa
    last: dict[str, float] = field(default_factory=dict)  # por chave, no relógio da mesa


@dataclass
class _Table:
    lock: threading.Lock = field(default_factory=threading.Lock)
    version: int = 0  # sobe a cada gravação; quem espera compara com a que viu
    waiters: int = 0
    # Vagas de chamada ao LLM, uma por tipo ("say", "copilot"): um tipo não segura o outro.
    slots: dict[str, _Slot] = field(default_factory=dict)
    presentation: Presentation = field(default_factory=lambda: Presentation(0))
    changed: threading.Condition = field(init=False)

    def __post_init__(self) -> None:
        self.changed = threading.Condition(self.lock)  # a mesma trava dos comandos


class Storage:
    """Onde as mesas moram (o banco), mais os locks, a espera por mudanças e os limites do LLM em memória."""

    def __init__(
        self,
        db: Database,
        *,
        max_tables: int,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
    ) -> None:
        self._db = db
        self._clock = clock  # injetável: os testes do intervalo do texto livre não esperam
        self._wall_clock = (
            wall_clock  # semente dos números do mural de falas e carimbo das gravações
        )
        self.max_tables = max_tables
        self._tables: dict[str, _Table] = {}
        self._registry = threading.Lock()

    # --- o banco -----------------------------------------------------------------

    def exists(self, table_id: str, *, scope: Scope = "active") -> bool:
        """A mesa existe? Por padrão só conta a ativa (a que se joga); ``scope`` pede a arquivada ou qualquer uma.

        Id fora do formato gerado aqui nunca chega ao banco.
        """
        if not TABLE_ID.match(table_id):
            return False
        return self._db.read(
            lambda s: (
                s.scalar(select(GameTable.id).where(GameTable.id == table_id, _in(scope)))
                is not None
            )
        )

    def read(self, table_id: str, *, scope: Scope = "active") -> Record | None:
        """O que está guardado da mesa, ou nada se ela não existe (no ``scope`` pedido)."""
        if not TABLE_ID.match(table_id):
            return None

        def read(session: Session) -> Record | None:
            row = session.execute(
                select(
                    GameTable.campaign_path, GameTable.state, GameTable.meta, GameTable.content
                ).where(GameTable.id == table_id, _in(scope))
            ).one_or_none()
            return None if row is None else Record(*row)

        return self._db.read(read)

    def create(self, table_id: str, record: Record, *, updated_at: float | None = None) -> bool:
        """Guarda uma mesa nova; ``False`` (e nada guardado) se o servidor já tem ``max_tables`` mesas ativas.

        A conferência do limite e a gravação são uma transação só: duas criações juntas não passam do limite.
        ``updated_at`` só serve à importação, que guarda a data do arquivo original.
        """
        now = self._wall_clock() if updated_at is None else updated_at

        def insert(session: Session) -> bool:
            if _active_count(session) >= self.max_tables:
                return False
            session.add(
                GameTable(
                    id=table_id,
                    campaign_path=record.campaign_path,
                    state=record.state,
                    meta=record.meta,
                    content=record.content,
                    created_at=now,
                    updated_at=now,
                )
            )
            return True

        return self._db.write(insert)

    def save(self, table_id: str, record: Record) -> None:
        """Regrava uma mesa ativa. Chamar com o lock dela tomado.

        ``404`` se ela foi apagada ou arquivada no meio do caminho: gravar não a traz de volta.
        """

        def write(session: Session) -> int:
            result = session.execute(
                update(GameTable)
                .where(GameTable.id == table_id, _in("active"))
                .values(
                    campaign_path=record.campaign_path,
                    state=record.state,
                    meta=record.meta,
                    content=record.content,
                    updated_at=self._wall_clock(),
                )
                .returning(GameTable.id)
            )
            return len(result.all())

        if self._db.write(write) == 0:
            raise ApiFailure(404, "table_not_found", "mesa não encontrada")

    def archive(self, table_id: str) -> bool:
        """Arquiva a mesa ativa (sai da lista, do jogo, do limite e da trava da campanha; o log fica). ``False`` se não há."""
        return self._flip(table_id, archiving=True)

    def restore(self, table_id: str) -> bool:
        """Traz de volta uma mesa arquivada. ``False`` se não há; ``409 table_limit`` se o servidor já tem o máximo ativo."""
        return self._flip(table_id, archiving=False)

    def _flip(self, table_id: str, *, archiving: bool) -> bool:
        """Arquiva (``archiving=True``, uma mesa ativa) ou restaura (``False``, uma arquivada); diz se havia o que mudar."""
        if not TABLE_ID.match(table_id):
            return False
        now = self._wall_clock()

        def write(session: Session) -> int:
            wanted: Scope = "active" if archiving else "archived"
            present = session.scalar(
                select(GameTable.id).where(GameTable.id == table_id, _in(wanted))
            )
            if present is None:
                return 0  # não há o que mudar (já estava assim, ou não existe)
            if (
                not archiving and _active_count(session) >= self.max_tables
            ):  # a vaga, na mesma transação
                raise ApiFailure(409, "table_limit", "este servidor já tem o máximo de mesas")
            changed = session.execute(
                update(GameTable)
                .where(GameTable.id == table_id, _in(wanted))
                .values(archived_at=now if archiving else None)
                .returning(GameTable.id)
            )
            return len(changed.all())

        return self._db.write(write) > 0

    def delete(self, table_id: str, *, scope: Scope = "archived") -> bool:
        """Apaga de vez; só a arquivada, por padrão (arquivar é o jeito de encerrar). ``False`` se não havia."""

        def remove(session: Session) -> int:
            gone = session.execute(
                delete(GameTable)
                .where(GameTable.id == table_id, _in(scope))
                .returning(GameTable.id)
            )
            return len(gone.all())

        return TABLE_ID.match(table_id) is not None and self._db.write(remove) > 0

    def updated_at(self, table_id: str) -> float:
        """Quando a mesa foi gravada pela última vez (0 se não existe)."""
        return (
            self._db.read(
                lambda s: s.scalar(select(GameTable.updated_at).where(GameTable.id == table_id))
            )
            or 0.0
        )

    def new_table_id(self) -> str:
        """Um id novo para uma mesa, que nenhuma outra (ativa ou arquivada) usa."""
        while True:
            table_id = secrets.token_hex(8)
            if not self.exists(table_id, scope="any"):
                return table_id

    def count(self) -> int:
        """Quantas mesas ativas existem."""
        return self._db.read(_active_count)

    def table_ids(self, *, scope: Scope = "active") -> list[str]:
        """Os ids das mesas, em ordem estável (só as ativas, por padrão)."""
        return self._db.read(
            lambda s: list(s.scalars(select(GameTable.id).where(_in(scope)).order_by(GameTable.id)))
        )

    def summaries(self, campaign_path: str, *, scope: Scope = "active") -> list[Summary]:
        """As mesas de uma campanha (``TableMeta`` em JSON, sem o estado), em ordem estável."""

        def read(session: Session) -> list[Summary]:
            rows = session.execute(
                select(GameTable.id, GameTable.meta, GameTable.updated_at, GameTable.archived_at)
                .where(GameTable.campaign_path == campaign_path, _in(scope))
                .order_by(GameTable.id)
            )
            return [Summary(*row) for row in rows]

        return self._db.read(read)

    def campaigns_in_use(self) -> set[str]:
        """Os caminhos de campanha (relativos à pasta de campanhas) que alguma mesa **ativa** usa.

        Mesa arquivada não trava a campanha: ao restaurá-la, a partida é conferida contra a campanha de então.
        """
        return self._db.read(
            lambda s: set(
                s.scalars(select(GameTable.campaign_path).where(_in("active")).distinct())
            )
        )

    # --- coordenação em memória --------------------------------------------------

    def _table(self, table_id: str) -> _Table:
        """O cadeado da mesa, criado na primeira vez.

        Uma entrada por mesa existente; o dicionário não cresce com ids inventados porque
        quem chama já validou o id com ``exists``.
        """
        with self._registry:
            if table_id not in self._tables:
                self._tables[table_id] = _Table(
                    presentation=Presentation(int(self._wall_clock() * 1000))
                )
            return self._tables[table_id]

    def lock(self, table_id: str) -> threading.Lock:
        """O lock de uma mesa: toda leitura e gravação do arquivo acontece com ele."""
        return self._table(table_id).lock

    def condition(self, table_id: str) -> threading.Condition:
        """Condição sobre o lock da mesa: ``wait`` solta o lock, então comandos seguem."""
        return self._table(table_id).changed

    def version(self, table_id: str) -> int:
        """O número de gravações da mesa desde a subida do servidor."""
        return self._table(table_id).version

    def announce_change(self, table_id: str) -> None:
        """Avisa quem espera que a mesa foi gravada. Chamar com o lock da mesa tomado."""
        table = self._table(table_id)
        table.version += 1
        table.changed.notify_all()

    def enter_slot(self, table_id: str, kind: str) -> bool:
        """Reserva a única chamada em curso de um tipo ao LLM na mesa.

        ``False`` se já há uma em curso: cada uma custa chamadas ao LLM de quem roda o servidor.
        """
        table = self._table(table_id)
        with self._registry:
            slot = table.slots.setdefault(kind, _Slot())
            if slot.busy:
                return False
            slot.busy = True
            return True

    def leave_slot(self, table_id: str, kind: str) -> None:
        """Libera a chamada ao LLM que estava em curso."""
        table = self._table(table_id)
        with self._registry:
            table.slots.setdefault(kind, _Slot()).busy = False

    def slot_cooldown_left(self, table_id: str, kind: str, key: str, cooldown: float) -> float:
        """Quanto falta até poder fazer outra chamada ao LLM.

        São segundos para ``key`` (o jogador, ou a mesa) poder pedir de novo; 0 se já pode.
        """
        table = self._table(table_id)
        with self._registry:
            last = table.slots.setdefault(kind, _Slot()).last.get(key)
            if last is None:
                return 0.0
            return max(0.0, cooldown - (self._clock() - last))

    def mark_slot(self, table_id: str, kind: str, key: str) -> None:
        """Anota que `key` acabou de fazer uma chamada ao LLM deste tipo."""
        table = self._table(table_id)
        with self._registry:
            table.slots.setdefault(kind, _Slot()).last[key] = self._clock()

    def presentation(self, table_id: str) -> Presentation:
        """Narração e mural da mesa (em memória). Só para mesa existente: o id já foi validado."""
        return self._table(table_id).presentation

    def now(self) -> float:
        """O relógio monotônico da mesa: prazos de espera e intervalos usam este."""
        return self._clock()

    def waiting(self, table_id: str) -> int:
        """Quantas esperas de long-poll há agora na mesa."""
        table = self._table(table_id)
        with self._registry:
            return table.waiters

    def enter_wait(self, table_id: str) -> bool:
        """Reserva uma vaga de espera; ``False`` se a mesa já tem ``MAX_WAITERS``."""
        table = self._table(table_id)
        with self._registry:
            if table.waiters >= MAX_WAITERS:
                return False
            table.waiters += 1
            return True

    def leave_wait(self, table_id: str) -> None:
        """Termina uma espera de long-poll."""
        table = self._table(table_id)
        with self._registry:
            table.waiters -= 1
