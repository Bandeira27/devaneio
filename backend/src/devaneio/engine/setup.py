"""Criação do estado inicial de uma partida a partir da campanha e do sistema de regras."""

from __future__ import annotations

from typing import Iterable

from devaneio.rng import Rng
from devaneio.rules import ExpressionError, RuleSystem, evaluate, parse
from devaneio.schema import BeatStatus, Campaign, Character, GameState, NpcState

from .attributes import resolve_attributes
from .errors import EngineError


def initial_state(
    campaign: Campaign,
    rules: RuleSystem,
    rng_seed: int,
    characters: Iterable[Character] = (),
) -> GameState:
    """Turno 0, NPCs nos locais de origem com atributos completos (campanha + defaults do
    sistema) e hp = max_hp pela fórmula do sistema; todos os marcos pendentes (quem ativa
    marcos é o diretor de narrativa).

    Se a fórmula de max_hp tiver dados, os sorteios saem do mesmo Rng do estado e
    ``rng_draws`` reflete isso. Atributo de NPC inválido para o sistema é ``EngineError``.
    """
    rng = Rng(rng_seed)
    max_hp_formula = parse(rules.max_hp)

    npcs: dict[str, NpcState] = {}
    for npc in campaign.npcs:
        attributes = resolve_attributes(rules, npc.attributes, f"npc '{npc.id}'")
        try:
            max_hp = evaluate(max_hp_formula, attributes, rng).total
        except ExpressionError as exc:
            raise EngineError(f"max_hp de '{npc.id}': {exc}") from exc
        if max_hp < 1:
            raise EngineError(f"max_hp de '{npc.id}' deu {max_hp}; precisa ser >= 1")
        npcs[npc.id] = NpcState(
            hp=max_hp, max_hp=max_hp, attributes=attributes, location_id=npc.location_id
        )

    return GameState(
        campaign_id=campaign.id,
        rng_seed=rng_seed,
        rng_draws=rng.draws,
        current_location_id=campaign.start_location_id,
        characters={c.id: c for c in characters},
        npcs=npcs,
        beats={b.id: BeatStatus.PENDING for b in campaign.beats},
    )
