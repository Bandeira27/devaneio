"""Esquema de dados: campanha (estática) e estado de jogo (mutável)."""

from .campaign import Beat, Campaign, Faction, Location, Npc
from .campaign_validation import CampaignIntegrityError, load_campaign, validate_campaign
from .common import Id, StrictModel
from .game_state import BeatStatus, Character, Event, Fact, GameState, NpcState
from .state_validation import initial_state, validate_against_campaign

__all__ = [
    "Beat",
    "BeatStatus",
    "Campaign",
    "CampaignIntegrityError",
    "Character",
    "Event",
    "Faction",
    "Fact",
    "GameState",
    "Id",
    "Location",
    "Npc",
    "NpcState",
    "StrictModel",
    "initial_state",
    "load_campaign",
    "validate_against_campaign",
    "validate_campaign",
]
