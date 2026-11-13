"""Erro comum das ações do motor."""


class EngineError(ValueError):
    """Ação inválida para este estado/sistema (id desconhecido, fórmula não avaliável)."""
