"""Desfecho da partida, derivado do estado (sem campo novo no GameState).

O motor não se recusa a agir numa partida encerrada: quem orquestra (o CLI hoje, a API
depois) consulta ``game_status`` e decide o que permitir.
"""

from __future__ import annotations

from enum import Enum

from devaneio.schema import BeatStatus, GameState


class GameStatus(str, Enum):
    ACTIVE = "active"
    WON = "won"
    LOST = "lost"


def game_status(state: GameState) -> GameStatus:
    """Vitória: há marcos e todos concluídos (vale mesmo com o grupo caído, a história
    terminou). Derrota: há personagens e todos com hp 0. Senão, em andamento."""
    if state.beats and all(s is BeatStatus.DONE for s in state.beats.values()):
        return GameStatus.WON
    if state.characters and all(c.hp == 0 for c in state.characters.values()):
        return GameStatus.LOST
    return GameStatus.ACTIVE
