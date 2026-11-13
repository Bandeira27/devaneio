"""Saída do CLI: prosa do narrador e, abaixo, a linha mecânica entre colchetes."""

from __future__ import annotations

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
