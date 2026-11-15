"""Erros do pacote ``game`` que mais de um módulo levanta."""


class GameError(ValueError):
    """Problema ao criar ou abrir uma partida (arquivo incoerente, campanha incompatível)."""
