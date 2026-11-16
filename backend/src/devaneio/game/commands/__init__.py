"""Interpretador de comandos: função pura de (sessão, linha) para (nova sessão, texto).

Quem chama (o laço do CLI, um servidor) só lê, chama ``execute`` e mostra. Tudo que o jogador
pode fazer passa por aqui, então os testes cobrem o jogo inteiro sem terminal.
"""

from .actors import resolve_actor
from .errors import READ_ONLY, CommandError, GameOverError
from .execute import COMMANDS, execute, is_command
from .parsing import parse_line, split_actor

__all__ = [
    "COMMANDS",
    "READ_ONLY",
    "CommandError",
    "GameOverError",
    "execute",
    "is_command",
    "parse_line",
    "resolve_actor",
    "split_actor",
]
