"""Movimento do grupo entre locais conectados."""

from __future__ import annotations

from dataclasses import dataclass

from devaneio.schema import Campaign, Event, GameState

from .errors import EngineError


@dataclass(frozen=True)
class MoveResult:
    """O novo estado depois de o grupo andar."""

    state: GameState
    from_location_id: str
    to_location_id: str
    text: str


def move(state: GameState, campaign: Campaign, *, to_location_id: str) -> MoveResult:
    """O grupo anda junto (``current_location_id`` é do estado).

    Só para um local ligado ao atual por ``connections``; viagem sem conexão não é movimento, é
    outra ação.
    """
    locations = {loc.id: loc for loc in campaign.locations}
    here = locations.get(state.current_location_id)
    if here is None:
        raise EngineError(f"local atual '{state.current_location_id}' não existe na campanha")
    there = locations.get(to_location_id)
    if there is None:
        raise EngineError(f"local '{to_location_id}' não existe na campanha")
    if to_location_id == here.id:
        raise EngineError(f"o grupo já está em '{here.id}'")
    if to_location_id not in here.connections:
        exits = ", ".join(here.connections) or "nenhuma"
        raise EngineError(f"'{here.id}' não conecta a '{to_location_id}' (saídas: {exits})")

    text = f"O grupo vai de {here.name} para {there.name}."
    new_state = state.model_copy(deep=True)
    new_state.current_location_id = to_location_id
    new_state.events.append(
        Event(
            turn=state.turn,
            kind="move",
            text=text,
            data={"from_location_id": here.id, "to_location_id": to_location_id},
        )
    )
    return MoveResult(new_state, here.id, to_location_id, text)
