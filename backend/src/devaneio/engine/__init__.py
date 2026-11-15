"""Motor: ações sobre o GameState. Funções puras: recebem um estado, devolvem outro."""

from .beats import BeatResult, activate_beat, complete_beat, fail_beat
from .characters import AddCharacterResult, add_character
from .checks import CheckResult, classify_outcome, npc_check, resolve_check
from .conditions import HIT, holds
from .damage import DamageResult, TargetKind, apply_damage, deal_damage
from .director import (
    DirectorResult,
    advance_beats,
    direct,
    hostile_reactions,
    pass_turn,
    tension,
)
from .errors import EngineError
from .heal import HealResult, RestResult, heal, rest
from .lookup import npc_ids_at, npc_locations
from .movement import MoveResult, move
from .reveal import RevealResult, reveal_fact, reveal_facts
from .setup import initial_state
from .status import GameStatus, game_status
from .turns import end_turn

__all__ = [
    "HIT",
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
    "RevealResult",
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
    "npc_ids_at",
    "npc_locations",
    "pass_turn",
    "resolve_check",
    "rest",
    "reveal_fact",
    "reveal_facts",
    "tension",
]
