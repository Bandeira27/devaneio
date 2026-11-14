"""Esquema de dados: campanha (estática) e estado de jogo (mutável)."""

from .campaign import (
    AtLocation,
    Beat,
    BeatDone,
    Campaign,
    Condition,
    Faction,
    Location,
    Npc,
    NpcDown,
    TurnAtLeast,
)
from .campaign_validation import CampaignIntegrityError, load_campaign, validate_campaign
from .common import Id, StrictModel
from .game_state import BeatStatus, Character, Event, Fact, GameState, NpcState
from .state_validation import validate_against_campaign

__all__ = [
    "AtLocation",
    "Beat",
    "BeatDone",
    "BeatStatus",
    "Campaign",
    "CampaignIntegrityError",
    "Character",
    "Condition",
    "Event",
    "Fact",
    "Faction",
    "GameState",
    "Id",
    "Location",
    "Npc",
    "NpcDown",
    "NpcState",
    "StrictModel",
    "TurnAtLeast",
    "load_campaign",
    "validate_against_campaign",
    "validate_campaign",
]
