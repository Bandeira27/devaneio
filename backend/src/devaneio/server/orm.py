"""Modelos do ORM (SQLAlchemy): como o servidor guarda; não são os modelos do contrato (Pydantic).

O esquema real do arquivo vem das migrações (``migrations.py``); estes modelos descrevem o que elas
produzem, e um teste confere que os dois não se afastam.
"""

from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text
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


class ChatMessage(Base):
    """Uma mensagem do chat da mesa (só para o grupo; não é evento nem entra no estado da partida).

    ``name`` e ``role`` são os do jogador na hora de enviar. ``seq`` sobe de 1 em 1 por mesa e continua depois de um
    reinício. Some junto com a mesa apagada de vez.
    """

    __tablename__ = "chat_messages"

    table_id: Mapped[str] = mapped_column(
        String, ForeignKey("tables.id", ondelete="CASCADE"), primary_key=True
    )
    seq: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[str] = mapped_column(String, nullable=False)
    # Nulo = mensagem para a mesa toda; preenchido = sussurro, visto só por quem enviou e por este jogador.
    to_player_id: Mapped[str | None] = mapped_column(String, nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
