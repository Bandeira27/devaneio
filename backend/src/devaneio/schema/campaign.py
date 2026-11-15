"""Campanha: conteúdo estático que não muda durante a partida."""

from typing import Annotated, Literal

from pydantic import Field

from .common import Id, StrictModel


class Location(StrictModel):
    id: Id
    name: str
    description: str = ""
    # Conexões são direcionais: uma passagem de mão única é válida.
    connections: list[Id] = []
    # Notas do autor: só o anfitrião vê, nunca vão a jogadores nem ao LLM da mesa por padrão.
    private_notes: list[str] = []


class Faction(StrictModel):
    id: Id
    name: str
    description: str = ""
    goals: list[str] = []
    private_notes: list[str] = []


class Npc(StrictModel):
    id: Id
    name: str
    description: str = ""
    location_id: Id | None = None
    faction_id: Id | None = None
    private_notes: list[str] = []
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


class CheckPassed(StrictModel):
    """Algum personagem já passou (sucesso ou sucesso crítico) num teste desta habilidade.
    Testes de NPC não contam. Não exige local nem turno: combine com ``at_location`` etc."""

    kind: Literal["check_passed"]
    skill_id: Id


Condition = Annotated[
    AtLocation | NpcDown | BeatDone | TurnAtLeast | CheckPassed, Field(discriminator="kind")
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
    private_notes: list[str] = []


class FactDef(StrictModel):
    """Informação da campanha que começa privada (só o anfitrião sabe) e pode virar pública.

    ``about`` aponta um NPC, local, facção ou marco e serve só de rótulo de exibição.
    ``reveal_when``: o motor revela o fato quando todas as condições valem; vazia, só o
    anfitrião revela, por comando. O estado guarda apenas quais fatos já foram revelados.
    """

    id: Id
    text: str
    about: Id | None = None
    reveal_when: list[Condition] = []


class Campaign(StrictModel):
    schema_version: Literal[1] = 1
    id: Id
    title: str
    premise: str
    rules_id: Id = "default"
    # Pacote de narração (a voz do narrador); o embutido padrão é o pt-br.
    narration_id: Id = "pt-br"
    start_location_id: Id
    # Listas, não dicts: JSON com chave repetida é achatado silenciosamente pelo parser,
    # então detectar id duplicado (erro comum de autoria) exige lista.
    locations: list[Location] = []
    factions: list[Faction] = []
    npcs: list[Npc] = []
    beats: list[Beat] = []
    facts: list[FactDef] = []
