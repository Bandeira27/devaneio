"""LLM no papel de narrador: transforma os eventos mecânicos de uma ação em prosa.

Só exibição: o texto nunca volta para o estado, então prosa errada não corrompe a partida.
A saída é validada de forma grosseira (não vazia, curta, não-JSON); quem chama cai na
gramática se der erro.
"""

from __future__ import annotations

from collections.abc import Sequence

from devaneio.schema import Campaign, GameState

from .client import ChatClient
from .errors import LlmError

MAX_CHARS = 900
NARRATOR_SYSTEM = """\
Você narra um RPG de mesa em português do Brasil. Receberá os eventos mecânicos que acabaram
de acontecer. Escreva UM parágrafo curto (2 a 4 frases) em prosa.

Regras:
- Não mude nenhum fato, resultado ou número dos eventos; não invente acontecimentos além deles.
- Não revele segredos nem informações que os eventos não mostram.
- Sem listas, sem JSON, sem markdown, sem títulos.
"""


def build_narration_messages(
    campaign: Campaign, state: GameState, event_texts: Sequence[str]
) -> list[dict[str, str]]:
    here = next((loc for loc in campaign.locations if loc.id == state.current_location_id), None)
    place = f"{here.name}. {here.description}" if here else state.current_location_id
    party = ", ".join(c.name for c in state.characters.values()) or "ninguém"
    events = "\n".join(f"- {t}" for t in event_texts)
    return [
        {"role": "system", "content": NARRATOR_SYSTEM},
        {
            "role": "user",
            "content": f"Campanha: {campaign.title}\nLocal: {place}\nGrupo: {party}\n\nEventos:\n{events}",
        },
    ]


def clean_narration(raw: str) -> str:
    text = " ".join(raw.split())
    if not text:
        raise LlmError("narração vazia")
    if text.startswith(("{", "[", "```")):
        raise LlmError("a narração veio em formato de dados, não em prosa")
    if len(text) > MAX_CHARS:
        raise LlmError(f"narração longa demais ({len(text)} caracteres)")
    return text


def narrate_with_llm(
    client: ChatClient, campaign: Campaign, state: GameState, event_texts: Sequence[str]
) -> str:
    """Um parágrafo para o lote de eventos. ``LlmError`` em qualquer falha."""
    raw = client.complete(build_narration_messages(campaign, state, event_texts), temperature=0.8)
    return clean_narration(raw)
