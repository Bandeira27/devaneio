"""Campanha: conteúdo estático que não muda durante a partida."""

from typing import Annotated, Literal, Union

from pydantic import Field

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
    # Disposição inicial para com o grupo; abaixo de dispositions.hostile_below do sistema, ataca.
    disposition: int = 0
    # Arma com que ataca; sem ela, usa combat.default_weapon do sistema.
    weapon_id: Id | None = None


# Condições declarativas avaliadas pelo diretor sobre o estado. Todas as de uma lista
# precisam valer. Regras são dados: a campanha descreve a própria trama sem código.


class AtLocation(StrictModel):
    kind: Literal["at_location"]
    location_id: Id


class NpcDown(StrictModel):
    kind: Literal["npc_down"]
    npc_id: Id


class BeatDone(StrictModel):
    kind: Literal["beat_done"]
    beat_id: Id


class TurnAtLeast(StrictModel):
    kind: Literal["turn_at_least"]
    turn: int = Field(ge=0)


Condition = Annotated[
    Union[AtLocation, NpcDown, BeatDone, TurnAtLeast], Field(discriminator="kind")
]


class Beat(StrictModel):
    """Marco da trama. ``requires`` lista marcos que precisam estar concluídos antes.

    ``activate_when``: condições para passar de pendente a ativo (além dos requisitos);
    vazia, ativa assim que os requisitos estiverem concluídos.
    ``complete_when``: condições para concluir automaticamente; vazia, só conclui por ação
    explícita (o mestre/jogador decide).
    """

    id: Id
    title: str
    description: str = ""
    requires: list[Id] = []
    activate_when: list[Condition] = []
    complete_when: list[Condition] = []


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
