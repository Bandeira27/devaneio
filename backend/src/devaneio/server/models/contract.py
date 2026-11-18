"""Envelope do contrato: erro e os modelos que só existem para gerar o JSON Schema."""

from __future__ import annotations

from devaneio.schema import (
    Campaign,
    StrictModel,
)

from .campaign import CampaignSummary, CampaignView
from .editor import (
    EditorCampaign,
    PreviewView,
    SaveRequest,
    SystemInfo,
    ValidateRequest,
    ValidationReport,
)
from .requests import (
    CommandRequest,
    CopilotRequest,
    CreateTableRequest,
    InvitePreviewRequest,
    JoinRequest,
    LifecycleRequest,
    SayRequest,
)
from .responses import (
    CommandResult,
    CopilotAnswer,
    EventsView,
    InvitePreview,
    SayResult,
    TableCreated,
    TableJoined,
)
from .rules_view import RulesView
from .state import TableView


class ApiError(StrictModel):
    """Um erro da API: um código estável e a mensagem em português."""

    code: str
    message: str


class ErrorResponse(StrictModel):
    """O corpo de toda resposta de erro."""

    error: ApiError


class ApiRequests(StrictModel):
    """Todos os corpos de requisição, reunidos só para gerar o contrato."""

    create_table: CreateTableRequest
    join_table: JoinRequest
    invite_preview: InvitePreviewRequest
    command: CommandRequest
    lifecycle: LifecycleRequest
    say: SayRequest
    copilot: CopilotRequest
    editor_validate: ValidateRequest
    editor_save: SaveRequest


class ApiResponses(StrictModel):
    """Todas as respostas, reunidas só para gerar o contrato."""

    campaigns: list[CampaignSummary]
    table: TableView
    table_created: TableCreated
    table_joined: TableJoined
    invite_preview: InvitePreview
    command_result: CommandResult
    say_result: SayResult
    copilot_answer: CopilotAnswer
    events: EventsView
    campaign: Campaign
    campaign_view: CampaignView
    rules: RulesView
    editor_campaigns: list[EditorCampaign]
    editor_campaign: EditorCampaign
    editor_report: ValidationReport
    editor_systems: list[SystemInfo]
    editor_preview: PreviewView
    error: ErrorResponse
