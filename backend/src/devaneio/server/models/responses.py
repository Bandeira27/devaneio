"""Saída da API: criação da mesa, eventos, falas e resultados de comando."""

from __future__ import annotations

from pydantic import Field

from devaneio.engine import GameStatus
from devaneio.schema import (
    Id,
    StrictModel,
)

from .state import TableView


class TableCreated(StrictModel):
    table_id: Id
    host_token: str
    invite_code: str
    table: TableView


class EventView(StrictModel):
    """Evento do log para o cliente: sem ``data``. ``prose`` é sempre a narração da gramática
    do próprio evento. ``narration`` é o parágrafo do LLM para o lote de uma ação de texto
    livre, só no primeiro evento visível do lote (nos outros é ``None``) e só enquanto o
    servidor não reinicia. Os dois são exibição, nunca voltam ao estado, e são iguais para
    todos os jogadores."""

    index: int
    turn: int
    kind: str
    text: str
    prose: str
    narration: str | None = None


class TalkView(StrictModel):
    """Fala do mestre ou do NPC numa ação de texto livre: exibição, em memória, igual para todos.
    ``after`` é a revisão da mesa na hora (o cliente a encaixa entre os eventos) e ``to`` é o
    personagem que a provocou. Não é evento: o LLM nunca escreve no estado."""

    seq: int
    after: int
    to: Id
    text: str


class EventsView(StrictModel):
    revision: int
    events: list[EventView]
    # Falas com ``seq`` maior que ``since_talk``; ``talk_seq`` é a última (o cliente a devolve
    # em ``since_talk``). Os números sobem entre reinícios do servidor.
    talk: list[TalkView] = Field(default_factory=list)
    talk_seq: int = 0


class CommandResult(StrictModel):
    revision: int
    events: list[EventView]  # os que este comando (e o fim de turno automático) produziu
    text: str
    status: GameStatus
    turn_ended: bool


class SayResult(CommandResult):
    say: str  # fala do mestre/NPC: só exibida e só para quem enviou o texto
    commands: list[str]  # as ações que o LLM propôs e o motor aplicou


class CopilotAnswer(StrictModel):
    text: str  # só para o anfitrião que perguntou: nunca vai ao mural nem ao arquivo da mesa


class TableJoined(StrictModel):
    player_id: Id
    token: str
    table: TableView
