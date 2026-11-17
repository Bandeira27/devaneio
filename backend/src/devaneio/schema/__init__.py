"""Esquema de dados: campanha (estática) e estado de jogo (mutável)."""

from .campaign import (
    AtLocation,
    Beat,
    BeatDone,
    Campaign,
    CheckPassed,
    Condition,
    FactDef,
    Faction,
    Location,
    Npc,
    NpcDown,
    TurnAtLeast,
)
from .campaign_validation import CampaignIntegrityError, load_campaign, validate_campaign
from .common import ID_REGEX, Id, StrictModel
from .game_state import BeatStatus, Character, Event, GameState, NpcState
from .state_validation import validate_against_campaign

__all__ = [
    "ID_REGEX",
    "AtLocation",
    "Beat",
    "BeatDone",
    "BeatStatus",
    "Campaign",
    "CampaignIntegrityError",
    "Character",
    "CheckPassed",
    "Condition",
    "Event",
    "FactDef",
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
