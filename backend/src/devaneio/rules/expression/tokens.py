"""Tokenizador: quebra o texto de uma expressão em números, dados, atributos e operadores."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import ExpressionError

_TOKEN_RE = re.compile(
    r"\s*(?:(?P<dice>\d*d\d+)|(?P<int>\d+)|(?P<ident>[A-Z][A-Z0-9_]*)|(?P<op>[-+*()]))"
)


@dataclass(frozen=True)
class Token:
    """Um pedaço do texto: o tipo, o texto e a posição onde começa."""

    kind: str
    text: str
    pos: int


def tokenize(text: str) -> list[Token]:
    """Quebra o texto em tokens; caractere desconhecido é `ExpressionError`."""
    tokens: list[Token] = []
    pos = 0
    while pos < len(text):
        if text[pos:].isspace():
            break
        m = _TOKEN_RE.match(text, pos)
        if m is None:
            raise ExpressionError(f"caractere inesperado {text[pos]!r} na posição {pos}")
        kind = m.lastgroup or ""
        tokens.append(Token(kind, m.group(kind), m.start(kind)))
        pos = m.end()
    return tokens
