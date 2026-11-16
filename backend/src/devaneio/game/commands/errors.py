"""Erros do interpretador e a lista dos comandos que ainda valem com a partida encerrada."""

from __future__ import annotations

from devaneio.engine import GameStatus

from .labels import STATUS_LABELS

READ_ONLY = {"ajuda", "olhar", "ficha", "marcos", "fatos", "log"}


class CommandError(ValueError):
    """Comando inválido ou recusado pelo motor. O estado não muda."""


class GameOverError(CommandError):
    """A partida já terminou e o comando não é de consulta. O estado não muda."""

    def __init__(self, status: GameStatus) -> None:
        super().__init__(
            f"a partida terminou ({STATUS_LABELS[status]}); "
            f"só é possível: {', '.join(sorted(READ_ONLY))}"
        )
        self.status = status
