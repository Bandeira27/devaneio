import copy

import pytest

from devaneio.schema import Campaign

# Campanha mínima mas completa: 3 locais, 1 facção, 2 NPCs, 3 marcos encadeados.
_CAMPAIGN_DATA = {
    "id": "sombra-do-vale",
    "title": "A Sombra do Vale",
    "premise": "Um culto esquecido desperta nas ruínas acima da vila.",
    "start_location_id": "vila",
    "locations": [
        {"id": "vila", "name": "Vila de Pedra Alta", "connections": ["floresta"]},
        {"id": "floresta", "name": "Floresta Cinzenta", "connections": ["vila", "ruinas"]},
        {"id": "ruinas", "name": "Ruínas do Templo", "connections": ["floresta"]},
    ],
    "factions": [
        {
            "id": "culto",
            "name": "Culto da Sombra",
            "goals": ["despertar o deus adormecido"],
        }
    ],
    "npcs": [
        {"id": "ferreiro", "name": "Bram", "location_id": "vila"},
        {
            "id": "sacerdote",
            "name": "Irmão Vael",
            "location_id": "ruinas",
            "faction_id": "culto",
            "secrets": ["é o líder do culto"],
            "attributes": {"FOR": 3, "PRE": 4},
        },
    ],
    "beats": [
        {"id": "chegada", "title": "Chegada à vila"},
        {"id": "pista", "title": "A pista nas ruínas", "requires": ["chegada"]},
        {"id": "confronto", "title": "Confronto com o culto", "requires": ["pista"]},
    ],
}


@pytest.fixture
def campaign_data() -> dict:
    """Cópia fresca do dict da campanha, para o teste poder mutar à vontade."""
    return copy.deepcopy(_CAMPAIGN_DATA)


@pytest.fixture
def campaign(campaign_data: dict) -> Campaign:
    return Campaign.model_validate(campaign_data)


@pytest.fixture
def rules_data() -> dict:
    """Cópia fresca do sistema padrão como dict."""
    import json

    from devaneio.rules import builtin_rules_json

    return json.loads(builtin_rules_json("default"))


@pytest.fixture
def rules(rules_data: dict):
    from devaneio.rules import RuleSystem

    return RuleSystem.model_validate(rules_data)
