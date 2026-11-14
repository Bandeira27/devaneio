"""Validação de integridade da campanha (referências, duplicatas, ciclos).

Separada dos validators do Pydantic de propósito: um ``model_validator`` só consegue
levantar um erro, e aqui queremos reportar todos de uma vez.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import Any

from pydantic import ValidationError

from .campaign import AtLocation, Beat, BeatDone, Campaign, NpcDown


class CampaignIntegrityError(ValueError):
    """Campanha estruturalmente válida, mas incoerente. ``errors`` tem a lista completa."""

    def __init__(self, errors: Iterable[str]) -> None:
        self.errors = list(errors)
        super().__init__("Campanha inconsistente:\n" + "\n".join(f"- {e}" for e in self.errors))


def validate_campaign(campaign: Campaign) -> list[str]:
    """Confere a coerência interna da campanha. Lista vazia significa campanha válida."""
    errors: list[str] = []

    errors += _duplicates("locations", (x.id for x in campaign.locations))
    errors += _duplicates("factions", (x.id for x in campaign.factions))
    errors += _duplicates("npcs", (x.id for x in campaign.npcs))
    errors += _duplicates("beats", (x.id for x in campaign.beats))

    location_ids = {x.id for x in campaign.locations}
    faction_ids = {x.id for x in campaign.factions}
    beat_ids = {x.id for x in campaign.beats}

    if campaign.start_location_id not in location_ids:
        errors.append(f"start_location_id '{campaign.start_location_id}' não existe em locations")

    for loc in campaign.locations:
        for target in loc.connections:
            if target == loc.id:
                errors.append(f"local '{loc.id}' conecta a si mesmo")
            elif target not in location_ids:
                errors.append(f"local '{loc.id}' conecta a '{target}', que não existe")

    for npc in campaign.npcs:
        if npc.location_id is not None and npc.location_id not in location_ids:
            errors.append(f"npc '{npc.id}' está em '{npc.location_id}', que não existe")
        if npc.faction_id is not None and npc.faction_id not in faction_ids:
            errors.append(f"npc '{npc.id}' pertence a '{npc.faction_id}', que não existe")

    for beat in campaign.beats:
        for req in beat.requires:
            if req == beat.id:
                errors.append(f"marco '{beat.id}' requer a si mesmo")
            elif req not in beat_ids:
                errors.append(f"marco '{beat.id}' requer '{req}', que não existe")

    npc_ids = {x.id for x in campaign.npcs}
    for beat in campaign.beats:
        for field_name in ("activate_when", "complete_when"):
            for cond in getattr(beat, field_name):
                where = f"marco '{beat.id}', {field_name}"
                if isinstance(cond, AtLocation) and cond.location_id not in location_ids:
                    errors.append(f"{where}: local '{cond.location_id}' não existe")
                elif isinstance(cond, NpcDown) and cond.npc_id not in npc_ids:
                    errors.append(f"{where}: npc '{cond.npc_id}' não existe")
                elif isinstance(cond, BeatDone):
                    if cond.beat_id == beat.id:
                        errors.append(f"{where}: depende da própria conclusão")
                    elif cond.beat_id not in beat_ids:
                        errors.append(f"{where}: marco '{cond.beat_id}' não existe")

    errors += _beat_cycles(campaign.beats)
    return errors


def load_campaign(data: Any) -> Campaign:
    """Valida estrutura (Pydantic) e integridade. ``data`` é JSON (str/bytes) ou dict.

    Levanta ``pydantic.ValidationError`` para erro de estrutura e
    ``CampaignIntegrityError`` para erro de coerência.
    """
    if isinstance(data, (str, bytes, bytearray)):
        campaign = Campaign.model_validate_json(data)
    else:
        campaign = Campaign.model_validate(data)
    errors = validate_campaign(campaign)
    if errors:
        raise CampaignIntegrityError(errors)
    return campaign


def _duplicates(collection: str, ids: Iterable[str]) -> list[str]:
    counts = Counter(ids)
    return [f"{collection}: id duplicado '{id_}' ({n} vezes)" for id_, n in counts.items() if n > 1]


def _beat_cycles(beats: list[Beat]) -> list[str]:
    """Detecta ciclos em ``requires`` com DFS de três cores; reporta cada ciclo uma vez.

    Auto-requisitos e referências inexistentes já são reportados em outro lugar e
    ficam fora do grafo.
    """
    graph: dict[str, list[str]] = {}
    for beat in beats:
        graph.setdefault(beat.id, [])
    for beat in beats:
        graph[beat.id] += [r for r in beat.requires if r in graph and r != beat.id]

    WHITE, GRAY, BLACK = 0, 1, 2
    color = dict.fromkeys(graph, WHITE)
    stack: list[str] = []
    cycles: list[str] = []

    def visit(node: str) -> None:
        color[node] = GRAY
        stack.append(node)
        for nxt in graph[node]:
            if color[nxt] == WHITE:
                visit(nxt)
            elif color[nxt] == GRAY:
                cycle = [*stack[stack.index(nxt) :], nxt]
                cycles.append("ciclo entre marcos: " + " -> ".join(cycle))
        stack.pop()
        color[node] = BLACK

    for node in graph:
        if color[node] == WHITE:
            visit(node)
    return cycles


__all__ = [
    "CampaignIntegrityError",
    "ValidationError",
    "load_campaign",
    "validate_campaign",
]
