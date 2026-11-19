"""Falha de API: status HTTP e mensagem que pode ir ao cliente."""

from __future__ import annotations


class ApiFailure(Exception):
    """Falha com status HTTP definido e mensagem que pode ir ao cliente."""

    def __init__(
        self, status: int, code: str, message: str, *, retry_after: int | None = None
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.retry_after = retry_after  # segundos, para o cabeçalho Retry-After (503)


class DatabaseError(Exception):
    """O banco ou a pasta de dados não pode ser usado (dono, versão, outra instância): quem sobe mostra e sai."""
