"""Tokens e convite da mesa.

Gerados com ``secrets``, guardados só como hash, comparados em tempo constante. Nada aqui sabe de
HTTP além do formato do cabeçalho ``Authorization``.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from devaneio.game import Player, TableMeta


def new_token() -> str:
    """Um token novo e imprevisível para um jogador."""
    return secrets.token_urlsafe(32)


def new_invite() -> str:
    """Um código de convite novo e imprevisível."""
    return secrets.token_urlsafe(12)


def hash_secret(secret: str) -> str:
    """O hash de um token ou convite; só ele é guardado."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def bearer_token(header: str | None) -> str | None:
    """O token de um cabeçalho `Authorization: Bearer <token>`.

    Devolve ``None`` sem cabeçalho ou com outro esquema.
    """
    scheme, _, token = (header or "").strip().partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def find_player(table: TableMeta, token: str) -> tuple[str, Player] | None:
    """O jogador dono de um token.

    Percorre todos os jogadores sempre (sem sair no primeiro acerto), para o tempo não depender
    de qual token bateu.
    """
    digest = hash_secret(token)
    found: tuple[str, Player] | None = None
    for player_id, player in table.players.items():
        if hmac.compare_digest(digest, player.token_hash):
            found = (player_id, player)
    return found
