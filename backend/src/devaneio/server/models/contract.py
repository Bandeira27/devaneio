"""Envelope do contrato: erro e os modelos que só existem para gerar o JSON Schema."""

from __future__ import annotations

from devaneio.schema import (
    Campaign,
    StrictModel,
)

from .campaign import CampaignSummary, CampaignView
from .requests import CommandRequest, CopilotRequest, CreateTableRequest, JoinRequest, SayRequest
from .responses import (
    CommandResult,
    CopilotAnswer,
    EventsView,
    SayResult,
    TableCreated,
    TableJoined,
)
from .rules_view import RulesView
from .state import TableView


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
    rules: RulesView
    error: ErrorResponse
