"""Motor: ações sobre o GameState. Funções puras: recebem um estado, devolvem outro."""

from .beats import BeatResult, activate_beat, complete_beat, fail_beat
from .characters import AddCharacterResult, add_character
from .checks import CheckResult, classify_outcome, npc_check, resolve_check
from .damage import DamageResult, TargetKind, apply_damage, deal_damage
from .errors import EngineError
from .movement import MoveResult, move
from .setup import initial_state
from .turns import end_turn

__all__ = [
    "AddCharacterResult",
    "BeatResult",
    "CheckResult",
    "DamageResult",
    "EngineError",
    "MoveResult",
    "TargetKind",
    "activate_beat",
    "add_character",
    "apply_damage",
    "classify_outcome",
    "complete_beat",
    "deal_damage",
    "end_turn",
    "fail_beat",
    "initial_state",
    "move",
    "npc_check",
    "resolve_check",
]
