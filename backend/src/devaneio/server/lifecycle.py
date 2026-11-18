"""Mudança de fase da mesa pelo anfitrião: iniciar, pausar, retomar e encerrar.

Só o anfitrião muda a fase (403 para os outros). Sob o lock da mesa, confere que a mesa não andou desde a revisão que o
cliente viu, aplica a transição de ``game.lifecycle`` e grava; quem espera por novidades acorda pelo evento da transição.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from devaneio.game import LifecycleError, Session, TableMeta, change_phase, save_game

from .errors import ApiFailure
from .models import LifecycleRequest
from .storage import Storage
from .turns import authenticate


class LifecycleDesk:
    """A mudança de fase de uma mesa, com o relógio do servidor."""

    def __init__(
        self,
        storage: Storage,
        load: Callable[[Path], Session],
        clock: Callable[[], float],
    ) -> None:
        self._storage = storage
        self._load = load
        self._clock = clock

    def run(
        self, table_id: str, path: Path, token: str, request: LifecycleRequest
    ) -> tuple[Session, TableMeta, str]:
        """Aplica a transição e devolve a partida e a mesa novas e o id de quem pediu (o anfitrião)."""
        with self._storage.lock(table_id):
            session = self._load(path)
            table, player_id, player = authenticate(session, token)
            if player.role != "host":
                raise ApiFailure(403, "forbidden", "só o anfitrião muda a fase da partida")
            revision = len(session.state.events)
            if request.revision != revision:
                raise ApiFailure(
                    409,
                    "stale_revision",
                    f"a mesa está na revisão {revision}, não em {request.revision}: releia",
                )
            try:
                new_session, new_table = change_phase(session, table, request.action, self._clock())
            except LifecycleError as exc:
                raise ApiFailure(409, exc.code, str(exc)) from None
            save_game(new_session)
            self._storage.announce_change(table_id)
        return new_session, new_table, player_id
