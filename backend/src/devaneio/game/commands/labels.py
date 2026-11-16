"""Rótulos em português dos desfechos da partida e dos estados de marco."""

from __future__ import annotations

from devaneio.engine import GameStatus
from devaneio.schema import BeatStatus

STATUS_LABELS = {
    GameStatus.WON: "vitória: todos os marcos foram concluídos",
    GameStatus.LOST: "derrota: todo o grupo caiu",
}

BEAT_LABELS = {
    BeatStatus.PENDING: "pendente",
    BeatStatus.ACTIVE: "ativo",
    BeatStatus.DONE: "concluído",
    BeatStatus.FAILED: "falho",
}
