"""Mesa: quem joga uma partida em grupo.

Fica dentro do arquivo de partida (``SaveFile.table``), fora do contrato; o CLI preserva o campo
sem interpretá-lo.

Só hashes de segredo ficam aqui; token e convite em claro nunca são gravados. A política de turnos
(quem já agiu) vive em ``acted``: personagem → turno em que fez a ação principal. O ciclo de vida da mesa
(``phase``) e o tempo de jogo também ficam aqui; as transições vivem em ``lifecycle``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from devaneio.schema import Id, StrictModel

Role = Literal["host", "player"]
# A fase da mesa: sala de espera, em andamento, pausada ou encerrada. Eixo à parte do desfecho da história
# (``GameStatus``: ativa, vitória, derrota), que é derivado do estado e não é gravado.
Phase = Literal["lobby", "running", "paused", "ended"]


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
    # Ciclo de vida. O padrão é "em andamento": mesas gravadas antes da sala de espera continuam como estavam.
    phase: Phase = "running"
    # Relógio de jogo (segundos de época do servidor): quando começou, quanto já rodou e desde quando está rodando.
    # A pausa não conta; ``resumed_at`` só existe enquanto a fase é "running".
    started_at: float | None = None
    played_seconds: float = Field(default=0.0, ge=0)
    resumed_at: float | None = None

    def elapsed(self, now: float) -> int:
        """Quantos segundos a partida já rodou: o acumulado mais o trecho em andamento, se houver."""
        running = max(0.0, now - self.resumed_at) if self.resumed_at is not None else 0.0
        return int(self.played_seconds + running)
