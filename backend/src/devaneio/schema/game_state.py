"""Estado de jogo: tudo que muda durante a partida. Referencia a campanha por id."""

from enum import Enum
from typing import Any, Literal

from pydantic import Field, model_validator

from .common import Id, StrictModel


class BeatStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    DONE = "done"
    FAILED = "failed"


class Character(StrictModel):
    id: Id
    name: str
    # Genérico de propósito: quais atributos existem é definido pelo sistema de regras.
    attributes: dict[str, int] = {}
    hp: int
    max_hp: int = Field(ge=0)
    inventory: list[str] = []

    @model_validator(mode="after")
    def _hp_within_max(self) -> "Character":
        if self.hp > self.max_hp:
            raise ValueError(f"hp ({self.hp}) maior que max_hp ({self.max_hp})")
        return self


class NpcState(StrictModel):
    # hp 0 derruba o NPC (alive=False). Para personagens, hp 0 é "fora de combate";
    # morte é decisão narrativa, não do motor.
    alive: bool = True
    hp: int
    max_hp: int = Field(ge=0)
    # Resolvidos na criação do estado (campanha + defaults do sistema): o motor age só
    # sobre estado e regras, e efeitos futuros podem alterá-los.
    attributes: dict[str, int] = {}
    # Sem limites: os limiares (hostil, neutro, aliado...) virão do sistema de regras.
    disposition: int = 0
    location_id: Id | None = None

    @model_validator(mode="after")
    def _hp_within_max(self) -> "NpcState":
        if self.hp > self.max_hp:
            raise ValueError(f"hp ({self.hp}) maior que max_hp ({self.max_hp})")
        return self


class Event(StrictModel):
    """Entrada do log. Provisório: ``data`` é genérico até o motor de regras definir
    os tipos de evento (aí vira união discriminada por ``kind``)."""

    turn: int = Field(ge=0)
    kind: str
    text: str = ""
    data: dict[str, Any] = {}


class GameState(StrictModel):
    state_version: Literal[1] = 1
    campaign_id: Id
    turn: int = Field(default=0, ge=0)
    # Aleatoriedade reprodutível: mesma semente + mesmo número de sorteios = mesmo resultado.
    rng_seed: int
    rng_draws: int = Field(default=0, ge=0)
    current_location_id: Id
    # Dicts por id: o estado é produzido pelo motor, e a busca por id é o acesso comum.
    characters: dict[Id, Character] = {}
    npcs: dict[Id, NpcState] = {}
    beats: dict[Id, BeatStatus] = {}
    # Fato revelado -> turno da revelação. O texto vive na campanha (``Campaign.facts``).
    revealed_facts: dict[Id, int] = {}
    events: list[Event] = []

    @model_validator(mode="after")
    def _internal_consistency(self) -> "GameState":
        errors = [
            f"characters['{key}'] tem id '{char.id}'"
            for key, char in self.characters.items()
            if key != char.id
        ]
        if errors:
            raise ValueError("; ".join(errors))
        return self
