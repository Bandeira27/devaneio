"""Motor: ações sobre o GameState. Funções puras: recebem um estado, devolvem outro."""

from .checks import CheckResult, classify_outcome, resolve_check
from .damage import DamageResult, TargetKind, apply_damage, deal_damage
from .errors import EngineError
from .setup import initial_state
from .turns import end_turn

__all__ = [
    "CheckResult",
    "DamageResult",
    "EngineError",
    "TargetKind",
    "apply_damage",
    "classify_outcome",
    "deal_damage",
    "end_turn",
    "initial_state",
    "resolve_check",
]
