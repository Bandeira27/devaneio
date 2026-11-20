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
        return _check_passed(condition, state)
    raise EngineError(f"condição desconhecida: {condition!r}")


def _check_passed(condition: CheckPassed, state: GameState) -> bool:
    """Algum teste de personagem passou na habilidade (e, se a condição pede, no local).

    O local do teste sai do próprio log: o grupo está onde o último ``move`` o deixou, e antes de
    qualquer ``move`` está onde o primeiro saiu (ou onde está agora, se nunca se moveu).
    """
    moves = [e for e in state.events if e.kind == "move"]
    here = moves[0].data.get("from_location_id") if moves else state.current_location_id
    for event in state.events:
        if event.kind == "move":
            here = event.data.get("to_location_id")
        elif (
            event.kind == "check"
            and event.data.get("actor_kind") == "character"
            and event.data.get("skill_id") == condition.skill_id
            and event.data.get("outcome") in PASSED
            and (condition.location_id is None or here == condition.location_id)
        ):
            return True
    return False
