"""Orquestração do jogo: partida em disco, interpretador de comandos, texto livre e saída.

Nada aqui é terminal nem HTTP: ``cli`` e um servidor são clientes deste pacote.
"""

from devaneio.llm import ChatClient, LlmConfig, LlmError

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
from .content import load_campaign_content
from .errors import GameError
from .freeform import FreeformResult, LlmUnavailableError, run_freeform
from .output import format_output, narrate_batch, status_banner
from .session import Session, connect_llm, load_game, new_game, save_game
from .table import Player, Role, TableMeta

__all__ = [
    "COMMANDS",
    "READ_ONLY",
    "ChatClient",
    "CommandError",
    "FreeformResult",
    "GameError",
    "GameOverError",
    "LlmConfig",
    "LlmError",
    "LlmUnavailableError",
    "Player",
    "Role",
    "Session",
    "TableMeta",
    "connect_llm",
    "execute",
    "format_output",
    "is_command",
    "load_campaign_content",
    "load_game",
    "narrate_batch",
    "new_game",
    "parse_line",
    "run_freeform",
    "save_game",
    "split_actor",
    "status_banner",
]
