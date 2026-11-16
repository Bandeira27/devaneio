"""Avanço de turno."""

from __future__ import annotations

from devaneio.schema import Event, GameState


def end_turn(state: GameState) -> GameState:
    """Fecha o turno atual: registra o evento e incrementa ``turn``.

    Só isso, por enquanto; o que acontece entre turnos (recuperação, diretor de narrativa) virá
    em outra ação.
    """
    new_state = state.model_copy(deep=True)
    new_state.events.append(
        Event(turn=state.turn, kind="turn_end", text=f"Fim do turno {state.turn}")
    )
    new_state.turn = state.turn + 1
    return new_state
