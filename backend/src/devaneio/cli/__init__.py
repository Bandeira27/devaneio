"""Linha de comando para jogar: cria partidas, carrega/salva e interpreta comandos."""

from .commands import CommandError, execute
from .session import CliError, Session, load_game, new_game, save_game

__all__ = ["CliError", "CommandError", "Session", "execute", "load_game", "new_game", "save_game"]
