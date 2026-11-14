"""Motor: ações sobre o GameState. Funções puras: recebem um estado, devolvem outro."""

from .beats import BeatResult, activate_beat, complete_beat, fail_beat
from .characters import AddCharacterResult, add_character
from .checks import CheckResult, classify_outcome, npc_check, resolve_check
from .damage import DamageResult, TargetKind, apply_damage, deal_damage
from .director import (
    DirectorResult,
    advance_beats,
    direct,
    holds,
    hostile_reactions,
    pass_turn,
    tension,
)
from .errors import EngineError
from .heal import HealResult, RestResult, heal, rest
from .movement import MoveResult, move
from .setup import initial_state
from .status import GameStatus, game_status
from .turns import end_turn

__all__ = [
    "AddCharacterResult",
    "BeatResult",
    "CheckResult",
    "DamageResult",
    "DirectorResult",
    "EngineError",
    "GameStatus",
    "HealResult",
    "MoveResult",
    "RestResult",
    "TargetKind",
    "activate_beat",
    "add_character",
    "advance_beats",
    "apply_damage",
    "classify_outcome",
    "complete_beat",
    "deal_damage",
    "direct",
    "end_turn",
    "fail_beat",
    "game_status",
    "heal",
    "holds",
    "hostile_reactions",
    "initial_state",
    "move",
    "npc_check",
    "pass_turn",
    "rest",
    "resolve_check",
    "tension",
]
