"""Mesa: quem joga uma partida em grupo. Persistida dentro do arquivo de partida
(``SaveFile.table``), fora do contrato; o CLI preserva o campo sem interpretá-lo.

Só hashes de segredo ficam aqui; token e convite em claro nunca são gravados. A política
de turnos (quem já agiu) vive em ``acted``: personagem → turno em que fez a ação principal.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from devaneio.schema import Id, StrictModel

Role = Literal["host", "player"]


class Player(StrictModel):
    name: str
    role: Role
    token_hash: str
    character_ids: list[Id] = Field(default_factory=list)


class TableMeta(StrictModel):
    invite_hash: str
    players: dict[Id, Player] = Field(default_factory=dict)
    acted: dict[Id, int] = Field(default_factory=dict)
