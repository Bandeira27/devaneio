"""Mesa: quem joga uma partida em grupo.

Fica dentro do arquivo de partida (``SaveFile.table``), fora do contrato; o CLI preserva o campo
sem interpretá-lo.

Só hashes de segredo ficam aqui; token e convite em claro nunca são gravados. A política de turnos
(quem já agiu) vive em ``acted``: personagem → turno em que fez a ação principal.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from devaneio.schema import Id, StrictModel

Role = Literal["host", "player"]


class Player(StrictModel):
    """Um jogador da mesa: nome, papel e o hash do token (o token em si nunca é guardado)."""

    name: str
    role: Role
    token_hash: str
    character_ids: list[Id] = Field(default_factory=list)


class TableMeta(StrictModel):
    """A mesa dentro do arquivo da partida: convite, jogadores e quem já agiu no turno."""

    invite_hash: str
    players: dict[Id, Player] = Field(default_factory=dict)
    acted: dict[Id, int] = Field(default_factory=dict)
