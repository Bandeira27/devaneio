"""Prévia de uma campanha ainda não jogada: o que o jogador, o LLM e o copiloto receberiam.

Monta um estado inicial com um jogador de atributos padrão (a seed é fixa) e os contextos que o resto do jogo
montaria numa mesa de verdade. Não grava nada e não chama o LLM.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from devaneio.engine import initial_state
from devaneio.llm.copilot import MAX_CONTEXT_CHARS, build_copilot_context
from devaneio.llm.prompts import build_context
from devaneio.rules import RuleSystem
from devaneio.schema import Campaign, Character, GameState

PREVIEW_SEED = 0
PREVIEW_ACTOR = "jogador"


@dataclass(frozen=True)
class PreviewContexts:
    """O estado inicial e os contextos: o do LLM só com o público, o do LLM com segredos e o do copiloto.

    ``copilot_chars`` é o tamanho do contexto do copiloto (a campanha inteira, compacta) e ``copilot_limit``
    o teto a partir do qual o copiloto encolhe ou recusa.
    """

    state: GameState
    llm: dict[str, Any]
    llm_secrets: dict[str, Any]
    copilot_chars: int
    copilot_limit: int


def preview_contexts(campaign: Campaign, rules: RuleSystem) -> PreviewContexts:
    """Os contextos de uma campanha válida, como começariam numa mesa nova."""
    hero = Character(
        id=PREVIEW_ACTOR,
        name="Jogador",
        attributes={a.id: a.default for a in rules.attributes},
        hp=1,
        max_hp=1,
    )
    state = initial_state(campaign, rules, PREVIEW_SEED, [hero])
    copilot = build_copilot_context(campaign, rules, state)
    return PreviewContexts(
        state=state,
        llm=build_context(campaign, rules, state, hero.id, include_private=False),
        llm_secrets=build_context(campaign, rules, state, hero.id, include_private=True),
        copilot_chars=len(json.dumps(copilot, ensure_ascii=False, separators=(",", ":"))),
        copilot_limit=MAX_CONTEXT_CHARS,
    )
