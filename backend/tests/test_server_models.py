"""Modelos da API: nomes de jogador e a fronteira entre o estado completo e o do jogador."""

import pytest
from pydantic import ValidationError

from devaneio.schema import GameState
from devaneio.server.models import CreateTableRequest, JoinRequest, PlayerStateView

# O que um jogador comum nunca recebe de GameState, de propósito (ver PlayerStateView).
HIDDEN_FROM_PLAYERS = {"rng_seed", "rng_draws", "events", "facts"}


def test_every_game_state_field_is_either_shown_or_hidden_on_purpose():
    shown = set(PlayerStateView.model_fields)
    assert shown <= set(GameState.model_fields)
    assert set(GameState.model_fields) == shown | HIDDEN_FROM_PLAYERS
    assert not shown & HIDDEN_FROM_PLAYERS


FULLWIDTH_A = chr(0xFF21)  # letra A de largura total: NFKC a transforma em A comum


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ("Bia", "Bia"),
        ("  Bia   Luz  ", "Bia Luz"),
        (FULLWIDTH_A + "na", "Ana"),
        ("Zoe" + chr(0x0308), "Zo" + chr(0x00EB)),  # "e" + trema combinante vira "ë"
    ],
)
def test_names_are_normalized(raw, clean):
    assert JoinRequest(invite_code="x", name=raw).name == clean
    assert CreateTableRequest(campaign_id="sombra-do-vale", host_name=raw).host_name == clean


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        chr(0),
        chr(0x1B) + "[31mAna",
        "Ana" + chr(0x200B),
        "Ana" + chr(0x202E) + "evil",
        "A" + chr(10) + "na",
        "A" + chr(9) + "na",
        "x" * 41,
    ],
    ids=[
        "vazio",
        "espacos",
        "nul",
        "ansi",
        "zero-width",
        "bidi",
        "quebra-de-linha",
        "tab",
        "longo",
    ],
)
def test_names_with_control_or_invisible_characters_are_refused(raw):
    with pytest.raises(ValidationError):
        JoinRequest(invite_code="x", name=raw)
    with pytest.raises(ValidationError):
        CreateTableRequest(campaign_id="sombra-do-vale", host_name=raw)
