"""Modelos do ORM (SQLAlchemy): como o servidor guarda; não são os modelos do contrato (Pydantic).

O esquema real do arquivo vem das migrações (``migrations.py``); estes modelos descrevem o que elas
produzem, e um teste confere que os dois não se afastam.
"""

from __future__ import annotations

from sqlalchemy import Float, Index, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base declarativa dos modelos do servidor."""


class Setting(Base):
    """Uma configuração não secreta da máquina (chave e valor em texto). Segredos não ficam aqui."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class GameTable(Base):
    """Uma mesa: a partida (estado em JSON, com os eventos dentro) e a mesa em grupo (jogadores, fase, hashes).

    ``state`` é o ``GameState`` e ``meta`` a ``TableMeta``, ambos JSON de texto, validados pelos modelos do jogo ao
    abrir. ``campaign_path`` é relativo à pasta de campanhas. Tokens e convites só existem aqui como hash.
    """

    __tablename__ = "tables"
    __table_args__ = (Index("ix_tables_campaign_path", "campaign_path"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    campaign_path: Mapped[str] = mapped_column(String, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[float] = mapped_column(Float, nullable=False)
    # Nulo = ativa. Arquivada: fora da lista, do jogo, do limite e da trava da campanha; estado e log ficam.
    archived_at: Mapped[float | None] = mapped_column(Float, nullable=True)
