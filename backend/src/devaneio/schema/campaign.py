"""Campanha: conteúdo estático que não muda durante a partida."""

from typing import Literal

from .common import Id, StrictModel


class Location(StrictModel):
    id: Id
    name: str
    description: str = ""
    # Conexões são direcionais: uma passagem de mão única é válida.
    connections: list[Id] = []


class Faction(StrictModel):
    id: Id
    name: str
    description: str = ""
    goals: list[str] = []


class Npc(StrictModel):
    id: Id
    name: str
    description: str = ""
    location_id: Id | None = None
    faction_id: Id | None = None
    secrets: list[str] = []
    # Parcial: atributos ausentes recebem o default do sistema de regras ao criar o estado.
    attributes: dict[str, int] = {}


class Beat(StrictModel):
    """Marco da trama. `requires` lista marcos que precisam estar concluídos antes."""

    id: Id
    title: str
    description: str = ""
    requires: list[Id] = []


class Campaign(StrictModel):
    schema_version: Literal[1] = 1
    id: Id
    title: str
    premise: str
    rules_id: Id = "default"
    start_location_id: Id
    # Listas, não dicts: JSON com chave repetida é achatado silenciosamente pelo parser,
    # então detectar id duplicado (erro comum de autoria) exige lista.
    locations: list[Location] = []
    factions: list[Faction] = []
    npcs: list[Npc] = []
    beats: list[Beat] = []
