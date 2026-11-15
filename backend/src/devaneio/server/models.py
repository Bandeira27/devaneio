"""Modelos da API: requisições (entrada, estritas) e respostas (saída).

``ApiRequests`` e ``ApiResponses`` existem só para o contrato: ``export_schema`` gera um
JSON Schema por modo (validation e serialization). Nenhum modelo de ``game/table.py``
é alcançável a partir das respostas: hashes nunca saem do arquivo.
"""

from __future__ import annotations

import unicodedata
from typing import Annotated, Literal

from pydantic import BeforeValidator, Field

from devaneio.engine import GameStatus, npc_ids_at
from devaneio.game import Role
from devaneio.rules import RuleSystem
from devaneio.schema import (
    BeatStatus,
    Campaign,
    Character,
    GameState,
    Id,
    StrictModel,
)

MAX_NAME = 40
MAX_SEED = 2**53  # mesma faixa portável de new_game
TurnPolicy = Literal["one_action_per_character"]
TURN_POLICY: TurnPolicy = "one_action_per_character"


_FORBIDDEN_CATEGORIES = {"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"}


def clean_name(value: object) -> object:
    """Nome de jogador: NFKC, sem caracteres de controle, formatação ou separadores de
    linha (ANSI, zero-width, bidi), espaços colapsados. Sem isso, "Ana\u200b" passaria por
    outro jogador e o nome chegaria sujo ao log, ao prompt do LLM e à tela dos outros."""
    if not isinstance(value, str):
        return value
    text = unicodedata.normalize("NFKC", value)
    if any(unicodedata.category(ch) in _FORBIDDEN_CATEGORIES for ch in text):
        raise ValueError("o nome não pode ter caracteres de controle ou invisíveis")
    return " ".join(text.split())


PlayerName = Annotated[str, BeforeValidator(clean_name), Field(min_length=1, max_length=MAX_NAME)]


def clean_line(value: object) -> object:
    """Linha de comando: mesma regra dos nomes quanto a caracteres de controle e invisíveis
    (um nome de personagem entre aspas viraria ANSI ou bidi na tela dos outros), sem
    colapsar espaços, que podem estar entre aspas."""
    if not isinstance(value, str):
        return value
    text = unicodedata.normalize("NFKC", value).strip()
    if any(unicodedata.category(ch) in _FORBIDDEN_CATEGORIES for ch in text):
        raise ValueError("a linha não pode ter caracteres de controle ou invisíveis")
    return text


MAX_LINE = 500
CommandLine = Annotated[str, BeforeValidator(clean_line), Field(min_length=1, max_length=MAX_LINE)]


class CreateTableRequest(StrictModel):
    campaign_id: Id
    host_name: PlayerName
    seed: int | None = Field(default=None, ge=0, lt=MAX_SEED)


class JoinRequest(StrictModel):
    invite_code: str = Field(min_length=1, max_length=64)
    name: PlayerName


class CommandRequest(StrictModel):
    line: CommandLine
    # Número de eventos que o cliente viu: comando que muda a partida com revisão velha é recusado.
    revision: int = Field(ge=0)


class SayRequest(StrictModel):
    text: CommandLine
    revision: int = Field(ge=0)


class CopilotRequest(StrictModel):
    """Pergunta avulsa ao copiloto do anfitrião (sem estado: cada chamada leva o contexto atual)."""

    text: CommandLine


class CampaignSummary(StrictModel):
    id: Id
    title: str
    premise: str


def summarize(campaign: Campaign) -> CampaignSummary:
    return CampaignSummary(id=campaign.id, title=campaign.title, premise=campaign.premise)


class ExitView(StrictModel):
    id: Id
    name: str


class LocationView(StrictModel):
    id: Id
    name: str
    description: str
    exits: list[ExitView]


class NpcInfo(StrictModel):
    id: Id
    name: str


class BeatInfo(StrictModel):
    id: Id
    title: str


class FactInfo(StrictModel):
    id: Id
    text: str
    about: Id | None


class CampaignView(StrictModel):
    """A campanha para um jogador comum: só o que o ``olhar`` do CLI mostra (título, premissa,
    local atual com saídas, NPCs ali, marcos que já começaram e fatos já revelados). Fatos
    ocultos, ``private_notes``, facções, condições dos
    marcos, atributos, disposição, armas e a localização dos outros NPCs ficam com o
    anfitrião, que recebe a ``Campaign`` inteira."""

    id: Id
    title: str
    premise: str
    location: LocationView
    npcs: list[NpcInfo]
    beats: list[BeatInfo]
    facts: list[FactInfo]

    @classmethod
    def of(cls, campaign: Campaign, state: GameState) -> CampaignView:
        names = {loc.id: loc.name for loc in campaign.locations}
        here = next(loc for loc in campaign.locations if loc.id == state.current_location_id)
        present = npc_ids_at(state, here.id)
        return cls(
            id=campaign.id,
            title=campaign.title,
            premise=campaign.premise,
            location=LocationView(
                id=here.id,
                name=here.name,
                description=here.description,
                exits=[ExitView(id=c, name=names.get(c, c)) for c in here.connections],
            ),
            npcs=[NpcInfo(id=n.id, name=n.name) for n in campaign.npcs if n.id in present],
            beats=[
                BeatInfo(id=b.id, title=b.title)
                for b in campaign.beats
                if state.beats.get(b.id) not in (None, BeatStatus.PENDING)
            ],
            facts=[
                FactInfo(id=f.id, text=f.text, about=f.about)
                for f in campaign.facts
                if f.id in state.revealed_facts
            ],
        )


class PlayerView(StrictModel):
    id: Id
    name: str
    role: Role
    character_ids: list[Id]


class LlmView(StrictModel):
    """O LLM é do processo do servidor (ambiente de quem o roda); os jogadores veem se
    está ligado e para onde o contexto da partida vai, antes de entrar."""

    enabled: bool
    description: str | None = None
    notice: str | None = None
    secrets: bool = False  # os segredos dos NPCs vão ao LLM (e a fala dele chega a todos)


class NpcView(StrictModel):
    """NPC como o ``olhar`` o mostra: vivo, hp e se está hostil. Atributos e disposição
    numéricos (que revelam defesas e o limiar de hostilidade) ficam com o anfitrião."""

    alive: bool
    hp: int
    max_hp: int
    hostile: bool


class PlayerStateView(StrictModel):
    """O que um jogador comum vê do estado. Fica de fora: ``rng_seed``/``rng_draws`` (com eles
    o próximo sorteio seria previsível), ``events`` (vêm por ``EventView``, sem ``data``).
    ``revealed_facts`` vai inteiro: só tem fatos que o motor ou o anfitrião já tornou públicos. NPCs só os do local
    atual e só como ``NpcView``; marcos só os que já começaram. O anfitrião (mestre) recebe o
    ``GameState`` inteiro. Campo novo de ``GameState`` não chega aqui sem ser listado em
    ``of`` (e ``tests/test_server_models.py`` obriga a decidir)."""

    state_version: Literal[1]
    campaign_id: Id
    turn: int
    current_location_id: Id
    characters: dict[Id, Character]
    npcs: dict[Id, NpcView]
    beats: dict[Id, BeatStatus]
    revealed_facts: dict[Id, int]

    @classmethod
    def of(cls, state: GameState, rules: RuleSystem) -> PlayerStateView:
        here = state.current_location_id
        hostile_below = rules.dispositions.hostile_below
        return cls(
            state_version=state.state_version,
            campaign_id=state.campaign_id,
            turn=state.turn,
            current_location_id=here,
            characters=state.characters,
            npcs={
                k: NpcView(
                    alive=v.alive,
                    hp=v.hp,
                    max_hp=v.max_hp,
                    hostile=v.disposition < hostile_below,
                )
                for k, v in state.npcs.items()
                if k in npc_ids_at(state, here)
            },
            beats={k: v for k, v in state.beats.items() if v is not BeatStatus.PENDING},
            revealed_facts=state.revealed_facts,
        )


class TableView(StrictModel):
    table_id: Id
    role: Role  # o papel de quem pediu: escolhe o ramo de `state`
    campaign: CampaignSummary
    players: list[PlayerView]
    turn_policy: TurnPolicy
    acted: dict[Id, int]
    revision: int
    status: GameStatus
    llm: LlmView
    state: GameState | PlayerStateView


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


class ApiError(StrictModel):
    code: str
    message: str


class ErrorResponse(StrictModel):
    error: ApiError


class ApiRequests(StrictModel):
    create_table: CreateTableRequest
    join_table: JoinRequest
    command: CommandRequest
    say: SayRequest
    copilot: CopilotRequest


class ApiResponses(StrictModel):
    campaigns: list[CampaignSummary]
    table: TableView
    table_created: TableCreated
    table_joined: TableJoined
    command_result: CommandResult
    say_result: SayResult
    copilot_answer: CopilotAnswer
    events: EventsView
    campaign: Campaign
    campaign_view: CampaignView
    error: ErrorResponse
