"""Autenticação: leitura do ``Authorization: Bearer`` e busca do jogador pelo hash do token."""

import pytest

from devaneio.game import Player, TableMeta
from devaneio.server.auth import bearer_token, find_player, hash_secret


@pytest.mark.parametrize(
    ("header", "token"),
    [
        ("Bearer abc", "abc"),
        ("bearer abc", "abc"),
        ("  Bearer   abc  ", "abc"),
        ("Bearer", None),
        ("Bearer   ", None),
        ("Basic abc", None),
        ("", None),
    ],
)
def test_bearer_token_reads_only_the_bearer_scheme(header, token):
    assert bearer_token(header) == token


def test_bearer_token_is_none_without_the_header():
    assert bearer_token(None) is None


def test_find_player_returns_the_player_whose_hash_matches():
    table = TableMeta(
        invite_hash=hash_secret("convite"),
        players={
            "p1": Player(name="Ana", role="host", token_hash=hash_secret("token-ana")),
            "p2": Player(name="Bia", role="player", token_hash=hash_secret("token-bia")),
        },
    )
    assert find_player(table, "token-bia") == ("p2", table.players["p2"])
    assert find_player(table, "token-ana") == ("p1", table.players["p1"])
    assert find_player(table, "convite") is None
    # o hash gravado no arquivo não serve como token
    assert find_player(table, hash_secret("token-ana")) is None
