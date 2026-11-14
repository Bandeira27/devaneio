"""Orquestração do jogo: partida em disco, interpretador de comandos, texto livre e saída.

Nada aqui é terminal nem HTTP: ``cli`` e um servidor são clientes deste pacote.
"""

from .commands import COMMANDS, READ_ONLY, CommandError, execute, is_command
from .freeform import FreeformResult, run_freeform
from .output import format_output, status_banner
from .session import GameError, SaveFile, Session, load_game, new_game, save_game

__all__ = [
    "COMMANDS",
    "READ_ONLY",
    "CommandError",
    "FreeformResult",
    "GameError",
    "SaveFile",
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
