"""Marcos da trama: pendente → ativo → concluído | falho."""

from __future__ import annotations

from dataclasses import dataclass

from devaneio.schema import Beat, BeatStatus, Campaign, Event, GameState

from .errors import EngineError


@dataclass(frozen=True)
class BeatResult:
    state: GameState
    beat_id: str
    status: BeatStatus
    text: str


def activate_beat(state: GameState, campaign: Campaign, *, beat_id: str) -> BeatResult:
    """Pendente → ativo. Exige todos os ``requires`` concluídos. Não avalia
    ``activate_when``: isso é o diretor; aqui é a ação explícita."""
    beat = _beat(state, campaign, beat_id)
    _expect(state, beat_id, BeatStatus.PENDING)
    missing = [r for r in beat.requires if state.beats.get(r) is not BeatStatus.DONE]
    if missing:
        raise EngineError(f"marco '{beat_id}' exige concluídos: {', '.join(missing)}")
    return _set(state, beat, BeatStatus.ACTIVE, "beat_activated", f"Marco ativado: {beat.title}.")


def complete_beat(state: GameState, campaign: Campaign, *, beat_id: str) -> BeatResult:
    beat = _beat(state, campaign, beat_id)
    _expect(state, beat_id, BeatStatus.ACTIVE)
    return _set(state, beat, BeatStatus.DONE, "beat_done", f"Marco concluído: {beat.title}.")


def fail_beat(state: GameState, campaign: Campaign, *, beat_id: str) -> BeatResult:
    """Ativo → falho. Marcos que o exigem ficam inalcançáveis; é a campanha quem decide
    se isso faz sentido."""
    beat = _beat(state, campaign, beat_id)
    _expect(state, beat_id, BeatStatus.ACTIVE)
    return _set(state, beat, BeatStatus.FAILED, "beat_failed", f"Marco falhou: {beat.title}.")


def _beat(state: GameState, campaign: Campaign, beat_id: str) -> Beat:
    beat = next((b for b in campaign.beats if b.id == beat_id), None)
    if beat is None:
        raise EngineError(f"marco '{beat_id}' não existe na campanha")
    if beat_id not in state.beats:
        raise EngineError(f"marco '{beat_id}' não está no estado")
    return beat


def _expect(state: GameState, beat_id: str, status: BeatStatus) -> None:
    current = state.beats[beat_id]
    if current is not status:
        raise EngineError(
            f"marco '{beat_id}' está '{current.value}', precisava estar '{status.value}'"
        )


def _set(state: GameState, beat: Beat, status: BeatStatus, kind: str, text: str) -> BeatResult:
    new_state = state.model_copy(deep=True)
    new_state.beats[beat.id] = status
    new_state.events.append(
        Event(
            turn=state.turn, kind=kind, text=text, data={"beat_id": beat.id, "status": status.value}
        )
    )
    return BeatResult(new_state, beat.id, status, text)
