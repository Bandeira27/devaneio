"""Condições declarativas: avaliadas sobre o estado, sem efeito colateral."""

from __future__ import annotations

from devaneio.rules import CheckOutcome
from devaneio.schema import (
    AtLocation,
    BeatDone,
    BeatStatus,
    CheckPassed,
    Condition,
    GameState,
    NpcDown,
    TurnAtLeast,
)

from .errors import EngineError

# Os graus em que um teste conta como passado (acerto, condição ``check_passed``).
HIT = (CheckOutcome.SUCCESS, CheckOutcome.CRITICAL_SUCCESS)
PASSED = frozenset(o.value for o in HIT)


def holds(condition: Condition, state: GameState) -> bool:
    """Uma condição declarativa vale neste estado?"""
    if isinstance(condition, AtLocation):
        return state.current_location_id == condition.location_id
    if isinstance(condition, NpcDown):
        npc = state.npcs.get(condition.npc_id)
        return npc is not None and (not npc.alive or npc.hp == 0)
    if isinstance(condition, BeatDone):
        return state.beats.get(condition.beat_id) is BeatStatus.DONE
    if isinstance(condition, TurnAtLeast):
        return state.turn >= condition.turn
    if isinstance(condition, CheckPassed):
        return any(
            e.kind == "check"
            and e.data.get("actor_kind") == "character"
            and e.data.get("skill_id") == condition.skill_id
            and e.data.get("outcome") in PASSED
            for e in state.events
        )
    raise EngineError(f"condição desconhecida: {condition!r}")
