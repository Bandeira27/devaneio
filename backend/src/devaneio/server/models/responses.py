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
    """A mesa recém-criada: o id, o token do anfitrião (que só aparece aqui) e o convite."""

    table_id: Id
    host_token: str
    invite_code: str
    table: TableView


class EventView(StrictModel):
    """Um evento do log como o cliente o recebe.

    Sem ``data``. ``prose`` é sempre a narração da gramática do próprio evento. ``narration`` é
    o parágrafo do LLM para o lote de uma ação de texto livre, só no primeiro evento visível do
    lote (nos outros é ``None``). Os dois são exibição, nunca voltam ao estado, e são iguais para
    todos os jogadores.
    """

    index: int
    turn: int
    kind: str
    text: str
    prose: str
    narration: str | None = None


class TalkView(StrictModel):
    """Uma fala do mestre ou de um NPC.

    Vem de uma ação de texto livre e é igual para todos. ``after`` é a revisão da mesa na hora (o cliente a encaixa entre os eventos) e ``to`` é o
    personagem que a provocou. Não é evento: o LLM nunca escreve no estado.
    """

    seq: int
    after: int
    to: Id
    text: str


class EventsView(StrictModel):
    """Eventos e falas novos desde a última leitura, com as posições para a próxima."""

    revision: int
    events: list[EventView]
    # `talk_seq` é a última fala; o cliente a devolve em `since_talk`. Sobe entre reinícios.
    talk: list[TalkView] = Field(default_factory=list)
    talk_seq: int = 0


class CommandResult(StrictModel):
    """O resultado de um comando: o que ele produziu e como a mesa ficou."""

    revision: int
    events: list[EventView]  # os que este comando (e o fim de turno automático) produziu
    text: str
    status: GameStatus
    turn_ended: bool


class SayResult(CommandResult):
    """O resultado de um texto livre: o de um comando, mais a fala do mestre."""

    say: str  # fala do mestre/NPC: só exibida e só para quem enviou o texto
    commands: list[str]  # as ações que o LLM propôs e o motor aplicou


class CopilotAnswer(StrictModel):
    """A resposta do copiloto, só para o anfitrião."""

    text: str  # só para o anfitrião que perguntou: nunca vai ao mural nem ao arquivo da mesa


class InvitePreview(StrictModel):
    """O que um convite válido revela antes de entrar: o nome da mesa (o título da campanha), e nada mais."""

    title: str


class TableJoined(StrictModel):
    """A entrada numa mesa: o jogador, o token dele (que só aparece aqui) e a mesa."""

    player_id: Id
    token: str
    table: TableView
