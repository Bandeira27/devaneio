"""Falha de API: status HTTP e mensagem que pode ir ao cliente."""

from __future__ import annotations


class ApiFailure(Exception):
    """Falha com status HTTP definido e mensagem que pode ir ao cliente."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
