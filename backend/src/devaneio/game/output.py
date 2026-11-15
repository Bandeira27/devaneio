"""Saída da partida (o CLI mostra): prosa do narrador e, abaixo, a linha mecânica entre colchetes."""

from __future__ import annotations

from collections.abc import Sequence

from devaneio.engine import GameStatus, game_status
from devaneio.llm import ChatClient, LlmError, narrate_with_llm
from devaneio.narration import Narrator
from devaneio.schema import Campaign, GameState


def narrate_batch(
    client: ChatClient, campaign: Campaign, after: GameState, texts: Sequence[str]
) -> tuple[str | None, str]:
    """Um parágrafo do LLM para o lote de eventos e, se ele falhar, ``None`` e o aviso de que
    vale a gramática. É o único lugar com esse fallback: CLI e servidor o usam."""
    try:
        return narrate_with_llm(client, campaign, after, texts), ""
    except LlmError as exc:
        return None, f"(narração por LLM indisponível: {exc}; usei a gramática)"


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
        prose, note = narrate_batch(llm, narrator.campaign, after, [e.text for e in events])
        if prose is not None:
            return "\n".join([prose, *(f"  [{e.text}]" for e in events)])

    lines: list[str] = []
    for index, event in zip(indexes, events, strict=True):
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
