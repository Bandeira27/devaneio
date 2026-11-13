"""Saída do CLI: prosa do narrador e, abaixo, a linha mecânica entre colchetes."""

from __future__ import annotations

from devaneio.engine import GameStatus, game_status
from devaneio.llm import ChatClient, LlmError, narrate_with_llm
from devaneio.narration import Narrator
from devaneio.schema import GameState


def format_output(
    narrator: Narrator,
    before: GameState,
    after: GameState,
    fallback: str,
    llm: ChatClient | None = None,
) -> str:
    """Para os eventos novos: prosa e, abaixo, a linha mecânica de cada um entre colchetes.
    A prosa vem do LLM (um parágrafo para o lote) ou, sem LLM ou se ele falhar, da
    gramática, evento a evento. Sem evento novo (olhar, ficha, ajuda...), o texto do
    comando como veio."""
    indexes = range(len(before.events), len(after.events))
    if not indexes:
        return fallback
    events = [after.events[i] for i in indexes]

    note = ""
    if llm is not None:
        try:
            prose = narrate_with_llm(llm, narrator.campaign, after, [e.text for e in events])
            return "\n".join([prose, *(f"  [{e.text}]" for e in events)])
        except LlmError as exc:
            note = f"(narração por LLM indisponível: {exc}; usei a gramática)"

    lines: list[str] = []
    for index, event in zip(indexes, events):
        lines.append(narrator.narrate(event, index, after))
        lines.append(f"  [{event.text}]")
    if note:
        lines.append(note)
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
