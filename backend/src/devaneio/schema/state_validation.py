"""Coerência entre um GameState e a Campaign que ele referencia."""

from __future__ import annotations

from .campaign import Campaign
from .game_state import GameState


def validate_against_campaign(state: GameState, campaign: Campaign) -> list[str]:
    """Confere referências cruzadas. Lista vazia significa estado coerente com a campanha.

    Invariantes internos do estado (hp <= max_hp, chave == id) são garantidos pelo
    próprio modelo e não entram aqui.
    """
    errors: list[str] = []

    if state.campaign_id != campaign.id:
        errors.append(
            f"estado referencia campanha '{state.campaign_id}', mas a campanha é '{campaign.id}'"
        )

    location_ids = {x.id for x in campaign.locations}
    if state.current_location_id not in location_ids:
        errors.append(f"current_location_id '{state.current_location_id}' não existe na campanha")

    campaign_npcs = {x.id for x in campaign.npcs}
    for npc_id in sorted(set(state.npcs) - campaign_npcs):
        errors.append(f"npc '{npc_id}' no estado não existe na campanha")
    for npc_id in sorted(campaign_npcs - set(state.npcs)):
        errors.append(f"npc '{npc_id}' da campanha não tem estado")
    for npc_id, npc in state.npcs.items():
        if npc.location_id is not None and npc.location_id not in location_ids:
            errors.append(f"npc '{npc_id}' está em '{npc.location_id}', que não existe")

    campaign_beats = {x.id for x in campaign.beats}
    for beat_id in sorted(set(state.beats) - campaign_beats):
        errors.append(f"marco '{beat_id}' no estado não existe na campanha")
    for beat_id in sorted(campaign_beats - set(state.beats)):
        errors.append(f"marco '{beat_id}' da campanha não tem estado")

    campaign_facts = {x.id for x in campaign.facts}
    for fact_id in sorted(set(state.revealed_facts) - campaign_facts):
        errors.append(f"fato revelado '{fact_id}' não existe na campanha")

    return errors
