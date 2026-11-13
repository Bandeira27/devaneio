"""Linha de comando para jogar: cria partidas, carrega/salva e interpreta comandos."""

from .commands import CommandError, execute, is_command
from .freeform import FreeformResult, run_freeform
from .output import format_output, status_banner
from .session import CliError, Session, load_game, new_game, save_game

__all__ = [
    "CliError",
    "CommandError",
    "FreeformResult",
    "Session",
    "execute",
    "format_output",
    "is_command",
    "load_game",
    "new_game",
    "run_freeform",
    "save_game",
    "status_banner",
]
