"""Modelos da API: nomes de jogador e a fronteira entre o estado completo e o do jogador."""

import pytest
from pydantic import ValidationError

from devaneio.schema import GameState
from devaneio.server.models import CommandRequest, CreateTableRequest, JoinRequest, PlayerStateView

# O que um jogador comum nunca recebe de GameState, de propósito (ver PlayerStateView).
HIDDEN_FROM_PLAYERS = {"rng_seed", "rng_draws", "events"}


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


FULLWIDTH_FIM = "".join(chr(0xFF00 + ord(c) - 0x20) for c in "fim")  # largura total; NFKC dá "fim"


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ("olhar", "olhar"),
        ("  olhar  ", "olhar"),  # só as pontas: o miolo pode estar entre aspas
        ('entrar bia "Bia  Luz"', 'entrar bia "Bia  Luz"'),
        (FULLWIDTH_FIM, "fim"),  # largura total não escapa da regra do anfitrião
        ("bia: " + FULLWIDTH_FIM, "bia: fim"),
    ],
)
def test_command_lines_are_normalized_like_names_but_keep_inner_spaces(raw, clean):
    assert CommandRequest(line=raw, revision=0).line == clean


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "olhar" + chr(10) + "fim",
        "olhar" + chr(0),
        chr(0x1B) + "[31molhar",
        "olhar" + chr(0x200B),
        "entrar x " + chr(0x202E) + "B",
        "x" * 501,
    ],
    ids=["vazio", "espacos", "quebra-de-linha", "nul", "ansi", "zero-width", "bidi", "longo"],
)
def test_command_lines_with_control_or_invisible_characters_are_refused(raw):
    with pytest.raises(ValidationError):
        CommandRequest(line=raw, revision=0)


def test_a_command_line_that_is_not_text_is_refused():
    with pytest.raises(ValidationError):
        CommandRequest.model_validate({"line": 5, "revision": 0})


def test_a_name_that_is_not_text_is_refused():
    with pytest.raises(ValidationError):
        JoinRequest.model_validate({"invite_code": "x", "name": 5})
