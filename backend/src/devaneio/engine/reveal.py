"""Fatos da campanha: o motor decide quando um segredo vira público."""

from __future__ import annotations

from dataclasses import dataclass

from devaneio.schema import Campaign, Event, FactDef, GameState

from .conditions import holds
from .errors import EngineError


@dataclass(frozen=True)
class RevealResult:
    state: GameState
    fact_id: str
    text: str


def reveal_facts(state: GameState, campaign: Campaign) -> tuple[GameState, tuple[str, ...]]:
    """Revela cada fato ainda oculto cujo ``reveal_when`` (não vazio) vale por inteiro. Fato
    sem condições só o anfitrião revela (``reveal_fact``). Um evento ``reveal`` por fato."""
    texts: list[str] = []
    for fact in campaign.facts:
        if (
            fact.id not in state.revealed_facts
            and fact.reveal_when
            and all(holds(c, state) for c in fact.reveal_when)
        ):
            result = _reveal(state, fact)
            state = result.state
            texts.append(result.text)
    return state, tuple(texts)


def reveal_fact(state: GameState, campaign: Campaign, *, fact_id: str) -> RevealResult:
    """Ação explícita do anfitrião: revela o fato sem avaliar ``reveal_when``."""
    fact = next((f for f in campaign.facts if f.id == fact_id), None)
    if fact is None:
        raise EngineError(f"fato '{fact_id}' não existe na campanha")
    if fact_id in state.revealed_facts:
        raise EngineError(f"fato '{fact_id}' já foi revelado")
    return _reveal(state, fact)


def _reveal(state: GameState, fact: FactDef) -> RevealResult:
    new_state = state.model_copy(deep=True)
    new_state.revealed_facts[fact.id] = state.turn
    text = f"Revelado: {fact.text}"
    new_state.events.append(
        Event(turn=state.turn, kind="reveal", text=text, data={"fact_id": fact.id})
    )
    return RevealResult(new_state, fact.id, text)
