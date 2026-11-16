"""A mesa vista por um jogador: participantes, estado do jogo filtrado e aviso do LLM."""

from __future__ import annotations

from typing import Literal

from devaneio.engine import GameStatus, npc_ids_at
from devaneio.game import Role
from devaneio.rules import RuleSystem
from devaneio.schema import (
    BeatStatus,
    Character,
    GameState,
    Id,
    StrictModel,
)

from .campaign import CampaignSummary

TurnPolicy = Literal["one_action_per_character"]


TURN_POLICY: TurnPolicy = "one_action_per_character"


class PlayerView(StrictModel):
    """Um jogador da mesa, sem o hash do token."""

    id: Id
    name: str
    role: Role
    character_ids: list[Id]


class LlmView(StrictModel):
    """O LLM da mesa como os jogadores o veem.

    O LLM é do processo do servidor (ambiente de quem o roda); os jogadores veem se está ligado
    e para onde o contexto da partida vai, antes de entrar.
    """

    enabled: bool
    description: str | None = None
    notice: str | None = None
    secrets: bool = False  # os segredos dos NPCs vão ao LLM (e a fala dele chega a todos)


class NpcView(StrictModel):
    """Um NPC como o `olhar` o mostra.

    Vivo, hp e se está hostil. Atributos e disposição numéricos (que revelam defesas e o limiar
    de hostilidade) ficam com o anfitrião.
    """

    alive: bool
    hp: int
    max_hp: int
    hostile: bool


class PlayerStateView(StrictModel):
    """O estado do jogo como um jogador comum o vê.

    Fica de fora: ``rng_seed``/``rng_draws`` (com eles o próximo sorteio seria previsível),
    ``events`` (vêm por ``EventView``, sem ``data``). ``revealed_facts`` vai inteiro: só tem
    fatos que o motor ou o anfitrião já tornou públicos. NPCs só os do local atual e só como
    ``NpcView``; marcos só os que já começaram. O anfitrião (mestre) recebe o ``GameState``
    inteiro. Campo novo de ``GameState`` não chega aqui sem ser listado em ``of`` (e
    ``tests/test_server_models.py`` obriga a decidir).
    """

    state_version: Literal[1]
    campaign_id: Id
    turn: int
    current_location_id: Id
    characters: dict[Id, Character]
    npcs: dict[Id, NpcView]
    beats: dict[Id, BeatStatus]
    revealed_facts: dict[Id, int]

    @classmethod
    def of(cls, state: GameState, rules: RuleSystem) -> PlayerStateView:
        """O estado visto por um jogador comum, derivado do estado inteiro."""
        here = state.current_location_id
        hostile_below = rules.dispositions.hostile_below
        return cls(
            state_version=state.state_version,
            campaign_id=state.campaign_id,
            turn=state.turn,
            current_location_id=here,
            characters=state.characters,
            npcs={
                k: NpcView(
                    alive=v.alive,
                    hp=v.hp,
                    max_hp=v.max_hp,
                    hostile=v.disposition < hostile_below,
                )
                for k, v in state.npcs.items()
                if k in npc_ids_at(state, here)
            },
            beats={k: v for k, v in state.beats.items() if v is not BeatStatus.PENDING},
            revealed_facts=state.revealed_facts,
        )


class TableView(StrictModel):
    """A mesa: campanha, jogadores, turno, estado e o aviso do LLM, como o papel de quem pergunta vê."""

    table_id: Id
    role: Role  # o papel de quem pediu: escolhe o ramo de `state`
    campaign: CampaignSummary
    players: list[PlayerView]
    turn_policy: TurnPolicy
    acted: dict[Id, int]
    revision: int
    status: GameStatus
    llm: LlmView
    you: Id  # o ``player_id`` de quem pediu: o cliente não tem como saber qual PlayerView é o dele
    state: GameState | PlayerStateView
