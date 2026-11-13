"""Motor: ações sobre o GameState. Funções puras: recebem um estado, devolvem outro."""

from .characters import AddCharacterResult, add_character
from .checks import CheckResult, classify_outcome, npc_check, resolve_check
from .damage import DamageResult, TargetKind, apply_damage, deal_damage
from .errors import EngineError
from .movement import MoveResult, move
from .setup import initial_state
from .turns import end_turn

__all__ = [
    "AddCharacterResult",
    "CheckResult",
    "DamageResult",
    "EngineError",
    "MoveResult",
    "TargetKind",
    "add_character",
    "apply_damage",
    "classify_outcome",
    "deal_damage",
    "end_turn",
    "initial_state",
    "move",
    "npc_check",
    "resolve_check",
]
