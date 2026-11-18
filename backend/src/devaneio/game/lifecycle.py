"""Ciclo de vida da mesa: sala de espera, em andamento, pausada e encerrada.

A mesa nasce na sala de espera: convidados entram e criam personagem, mas a história não começou (nenhuma abertura, nenhum
marco ativo). O anfitrião inicia, pausa, retoma e encerra. Cada transição vira um evento no log (o jogador vê "Partida
pausada." no feed e a revisão muda, o que acorda quem espera) e o tempo de jogo só corre enquanto a fase é "running".

Tudo aqui é composição: o estado da história continua sendo coisa do motor, e a fase mora na mesa (``TableMeta``).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Literal

from devaneio.engine import advance_beats, reveal_facts
from devaneio.schema import Event

from .errors import GameError
from .session import Session
from .table import Phase, TableMeta

Action = Literal["start", "pause", "resume", "end"]

# (fase atual, ação) → fase nova. Qualquer outro par é uma transição inválida.
TRANSITIONS: dict[tuple[Phase, Action], Phase] = {
    ("lobby", "start"): "running",
    ("running", "pause"): "paused",
    ("paused", "resume"): "running",
    ("lobby", "end"): "ended",
    ("running", "end"): "ended",
    ("paused", "end"): "ended",
}

# O que o log diz de cada transição (o texto é a "prosa": o narrador cai nele para tipos sem regra).
EVENT_TEXTS: dict[Action, tuple[str, str]] = {
    "start": ("table_started", "A partida começou."),
    "pause": ("table_paused", "O anfitrião pausou a partida."),
    "resume": ("table_resumed", "O anfitrião retomou a partida."),
    "end": ("table_ended", "O anfitrião encerrou a partida."),
}


class LifecycleError(GameError):
    """Transição que a mesa não aceita agora; ``code`` é o código estável que o servidor devolve."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _refusal(phase: Phase, action: Action) -> LifecycleError:
    if phase == "ended":
        return LifecycleError("ended", "a partida já foi encerrada")
    messages: dict[Action, str] = {
        "start": "a partida já começou",
        "pause": "só dá para pausar uma partida em andamento",
        "resume": "a partida não está pausada",
        "end": "a partida já foi encerrada",
    }
    return LifecycleError("invalid_transition", messages[action])


def change_phase(
    session: Session, table: TableMeta, action: Action, now: float
) -> tuple[Session, TableMeta]:
    """Aplica uma transição: devolve a partida e a mesa novas, sem mexer nas de entrada.

    ``start`` exige ao menos um personagem (409 ``no_characters``) e roda a abertura da história (marcos que já
    podem começar, fatos que já se revelam). ``now`` é o relógio do servidor, em segundos.
    """
    target = TRANSITIONS.get((table.phase, action))
    if target is None:
        raise _refusal(table.phase, action)
    if action == "start" and not session.state.characters:
        raise LifecycleError("no_characters", "crie ao menos um personagem antes de iniciar")
    kind, text = EVENT_TEXTS[action]
    state = session.state
    state = state.model_copy(
        update={"events": [*state.events, Event(turn=state.turn, kind=kind, text=text)]}
    )
    if action == "start":
        state, _ = advance_beats(state, session.campaign)
        state, _ = reveal_facts(state, session.campaign)
    updated = _clock(table, action, now).model_copy(update={"phase": target})
    return replace(session, state=state, table=updated), updated


def _clock(table: TableMeta, action: Action, now: float) -> TableMeta:
    """O relógio de jogo depois da transição: abre o trecho ao iniciar e retomar, fecha ao pausar e encerrar."""
    if action == "start":
        return table.model_copy(update={"started_at": now, "resumed_at": now})
    if action == "resume":
        return table.model_copy(update={"resumed_at": now})
    played = table.played_seconds
    if table.resumed_at is not None:
        played += max(0.0, now - table.resumed_at)
    return table.model_copy(update={"played_seconds": played, "resumed_at": None})
