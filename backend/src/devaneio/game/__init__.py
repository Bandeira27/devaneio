"""Orquestração do jogo: partida em disco, interpretador de comandos, texto livre e saída.

Nada aqui é terminal nem HTTP: ``cli`` e um servidor são clientes deste pacote.
"""

from devaneio.llm import (
    ChatClient,
    CopilotContextTooLarge,
    LlmConfig,
    LlmError,
    ask_copilot,
    clean_text,
)

from .authoring import (
    CampaignCheck,
    Finding,
    check_campaign_data,
    check_content,
    explain_validation_error,
)
from .commands import (
    COMMANDS,
    READ_ONLY,
    CommandError,
    GameOverError,
    execute,
    is_command,
    parse_line,
    split_actor,
)
from .content import (
    load_campaign_content,
    load_pack_for,
    load_rules_by_id,
    load_rules_for,
    rules_ids,
)
from .errors import GameError
from .freeform import FreeformResult, LlmUnavailableError, run_freeform
from .output import format_output, narrate_batch, status_banner
from .preview import PreviewContexts, preview_contexts
from .session import Session, connect_llm, load_game, new_game, save_game, saved_campaign_path
from .table import Player, Role, TableMeta

__all__ = [
    "COMMANDS",
    "READ_ONLY",
    "CampaignCheck",
    "ChatClient",
    "CommandError",
    "CopilotContextTooLarge",
    "Finding",
    "FreeformResult",
    "GameError",
    "GameOverError",
    "LlmConfig",
    "LlmError",
    "LlmUnavailableError",
    "Player",
    "PreviewContexts",
    "Role",
    "Session",
    "TableMeta",
    "ask_copilot",
    "check_campaign_data",
    "check_content",
    "clean_text",
    "connect_llm",
    "execute",
    "explain_validation_error",
    "format_output",
    "is_command",
    "load_campaign_content",
    "load_game",
    "load_pack_for",
    "load_rules_by_id",
    "load_rules_for",
    "narrate_batch",
    "new_game",
    "parse_line",
    "preview_contexts",
    "rules_ids",
    "run_freeform",
    "save_game",
    "saved_campaign_path",
    "split_actor",
    "status_banner",
]
