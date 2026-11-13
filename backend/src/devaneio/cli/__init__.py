"""Linha de comando para jogar: cria partidas, carrega/salva e interpreta comandos."""

from .commands import CommandError, execute
from .output import format_output
from .session import CliError, Session, load_game, new_game, save_game

__all__ = ["CliError", "CommandError", "Session", "execute", "format_output", "load_game", "new_game", "save_game"]
