"""Saída do CLI: prosa do narrador e, abaixo, a linha mecânica entre colchetes."""

from __future__ import annotations

from devaneio.engine import GameStatus, game_status
from devaneio.narration import Narrator
from devaneio.schema import GameState


def format_output(narrator: Narrator, before: GameState, after: GameState, fallback: str) -> str:
    """Para cada evento novo, narração + ``[texto mecânico]``. Sem evento novo (olhar,
    ficha, ajuda...), o texto do comando como veio."""
    new_events = after.events[len(before.events):]
    if not new_events:
        return fallback
    lines: list[str] = []
    for index in range(len(before.events), len(after.events)):
        event = after.events[index]
        lines.append(narrator.narrate(event, index, after))
        lines.append(f"  [{event.text}]")
    return "\n".join(lines)


BANNERS = {
    GameStatus.WON: "*** VITÓRIA: todos os marcos foram concluídos. A história chega ao fim. ***",
    GameStatus.LOST: "*** DERROTA: todo o grupo caiu. A história termina aqui. ***",
}


def status_banner(before: GameState, after: GameState) -> str:
    """Aviso quando a ação acabou de encerrar a partida; vazio nos demais casos."""
    now = game_status(after)
    if game_status(before) is GameStatus.ACTIVE and now is not GameStatus.ACTIVE:
        return BANNERS[now]
    return ""
