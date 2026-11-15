"""`clean_text`: o que o LLM devolve perde o que engana ou suja a tela dos outros jogadores."""

import pytest

from devaneio.llm.text import clean_text


def test_plain_text_is_unchanged():
    assert clean_text("O vento muda de direção.") == "O vento muda de direção."


def test_accents_and_punctuation_survive():
    assert clean_text("Não! Será? — disse ele…") == "Não! Será? — disse ele…"


@pytest.mark.parametrize("raw", ["a\nb", "a\tb", "a\r\nb", "a  \n\t b", "a" + chr(0x2028) + "b"])
def test_any_whitespace_becomes_one_space(raw):
    assert clean_text(raw) == "a b"


def test_edges_are_trimmed():
    assert clean_text("  \n oi \t ") == "oi"


@pytest.mark.parametrize(
    "unsafe",
    [
        chr(0x1B),
        chr(0x00),
        chr(0x202E),
        chr(0x200B),
        chr(0x2066),
        chr(0xFEFF),
        chr(0xD800),
        chr(0xE000),
    ],
)
def test_control_format_surrogate_and_private_characters_vanish(unsafe):
    assert clean_text("a" + unsafe + "b") == "ab"


def test_an_ansi_escape_loses_only_the_escape_byte():
    assert clean_text(chr(0x1B) + "[2Jtexto") == "[2Jtexto"


def test_empty_and_only_unsafe_become_empty():
    assert clean_text("") == ""
    assert clean_text(chr(0x200B) + " \n" + chr(0x202E)) == ""
