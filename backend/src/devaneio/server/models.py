"""Modelos da API: requisições (entrada, estritas) e respostas (saída).

``ApiRequests`` e ``ApiResponses`` existem só para o contrato: ``export_schema`` gera um
JSON Schema por modo (validation e serialization). Nenhum modelo de ``game/table.py``
é alcançável a partir das respostas: hashes nunca saem do arquivo.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from devaneio.engine import GameStatus
from devaneio.game.table import Role
from devaneio.schema import Campaign, GameState, Id, StrictModel

MAX_NAME = 40
MAX_SEED = 2**53  # mesma faixa portável de new_game
TurnPolicy = Literal["one_action_per_character"]
TURN_POLICY: TurnPolicy = "one_action_per_character"


class CreateTableRequest(StrictModel):
    campaign_id: Id
    host_name: str = Field(min_length=1, max_length=MAX_NAME)
    seed: int | None = Field(default=None, ge=0, lt=MAX_SEED)


class CampaignSummary(StrictModel):
    id: Id
    title: str
    premise: str


def summarize(campaign: Campaign) -> CampaignSummary:
    return CampaignSummary(id=campaign.id, title=campaign.title, premise=campaign.premise)


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


class TableView(StrictModel):
    table_id: Id
    campaign: CampaignSummary
    players: list[PlayerView]
    turn_policy: TurnPolicy
    acted: dict[Id, int]
    revision: int
    status: GameStatus
    llm: LlmView
    state: GameState


class TableCreated(StrictModel):
    table_id: Id
    host_token: str
    invite_code: str
    table: TableView


class ApiError(StrictModel):
    code: str
    message: str


class ErrorResponse(StrictModel):
    error: ApiError


class ApiRequests(StrictModel):
    create_table: CreateTableRequest


class ApiResponses(StrictModel):
    campaigns: list[CampaignSummary]
    table: TableView
    table_created: TableCreated
    campaign: Campaign
    error: ErrorResponse
