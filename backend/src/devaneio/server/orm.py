"""Modelos do ORM (SQLAlchemy): como o servidor guarda; não são os modelos do contrato (Pydantic).

O esquema real do arquivo vem das migrações (``migrations.py``); estes modelos descrevem o que elas
produzem, e um teste confere que os dois não se afastam.
"""

from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base declarativa dos modelos do servidor."""


class Setting(Base):
    """Uma configuração não secreta da máquina (chave e valor em texto). Segredos não ficam aqui."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
