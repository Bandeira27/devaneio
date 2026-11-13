"""Motor: ações sobre o GameState. Funções puras: recebem um estado, devolvem outro."""

from .checks import CheckResult, EngineError, classify_outcome, resolve_check

__all__ = ["CheckResult", "EngineError", "classify_outcome", "resolve_check"]
