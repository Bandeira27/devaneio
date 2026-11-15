"""Orquestração do jogo: partida em disco, interpretador de comandos, texto livre e saída.

Nada aqui é terminal nem HTTP: ``cli`` e um servidor são clientes deste pacote.
"""

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
from .freeform import FreeformResult, run_freeform
from .output import format_output, status_banner
from .session import GameError, Session, load_game, new_game, save_game
from .table import Player, Role, TableMeta

__all__ = [
    "COMMANDS",
    "READ_ONLY",
    "CommandError",
    "FreeformResult",
    "GameError",
    "GameOverError",
    "Player",
    "Role",
    "Session",
    "TableMeta",
    "execute",
    "format_output",
    "is_command",
    "load_game",
    "new_game",
    "parse_line",
    "run_freeform",
    "save_game",
    "split_actor",
    "status_banner",
]
