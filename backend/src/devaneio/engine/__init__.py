"""Motor: ações sobre o GameState. Funções puras: recebem um estado, devolvem outro."""

from .checks import CheckResult, classify_outcome, resolve_check
from .errors import EngineError
from .setup import initial_state

__all__ = ["CheckResult", "EngineError", "classify_outcome", "initial_state", "resolve_check"]
