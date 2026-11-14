"""Expressões de dados: ``2d6 + FOR``, ``1d4 + FOR * 2``, ``(d20 - 3) * 2``.

Tokenizador e parser recursivo próprios; a AST é avaliada com um dicionário de atributos e
um ``Rng``. Nunca ``eval``: isto é tudo que uma fórmula pode fazer.

Gramática::

    expr   := term (("+" | "-") term)*
    term   := factor ("*" factor)*
    factor := INT | DICE | IDENT | "(" expr ")" | "-" factor
    DICE   := INT? "d" INT          (2d6, d20)
    IDENT  := [A-Z][A-Z0-9_]*       (ids de atributos)
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from devaneio.rng import Rng

MAX_DICE_COUNT = 100
MAX_DICE_SIDES = 1000


class ExpressionError(ValueError):
    """Erro de sintaxe ou de avaliação de uma expressão."""


# --- AST -------------------------------------------------------------------------


@dataclass(frozen=True)
class Num:
    value: int


@dataclass(frozen=True)
class Dice:
    count: int
    sides: int


@dataclass(frozen=True)
class Attr:
    name: str


@dataclass(frozen=True)
class Neg:
    operand: Node


@dataclass(frozen=True)
class BinOp:
    op: str  # "+", "-", "*"
    left: Node
    right: Node


Node = Num | Dice | Attr | Neg | BinOp


# --- Tokenizador -----------------------------------------------------------------

_TOKEN_RE = re.compile(
    r"\s*(?:(?P<dice>\d*d\d+)|(?P<int>\d+)|(?P<ident>[A-Z][A-Z0-9_]*)|(?P<op>[-+*()]))"
)


@dataclass(frozen=True)
class _Token:
    kind: str
    text: str
    pos: int


def _tokenize(text: str) -> list[_Token]:
    tokens: list[_Token] = []
    pos = 0
    while pos < len(text):
        if text[pos:].isspace():
            break
        m = _TOKEN_RE.match(text, pos)
        if m is None:
            raise ExpressionError(f"caractere inesperado {text[pos]!r} na posição {pos}")
        kind = m.lastgroup or ""
        tokens.append(_Token(kind, m.group(kind), m.start(kind)))
        pos = m.end()
    return tokens


# --- Parser ----------------------------------------------------------------------


class _Parser:
    def __init__(self, text: str) -> None:
        self.text = text
        self.tokens = _tokenize(text)
        self.i = 0

    def parse(self) -> Node:
        if not self.tokens:
            raise ExpressionError("expressão vazia")
        node = self._expr()
        if self.i < len(self.tokens):
            tok = self.tokens[self.i]
            raise ExpressionError(f"sobrou {tok.text!r} na posição {tok.pos}")
        return node

    def _peek(self) -> _Token | None:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def _take(self) -> _Token:
        tok = self._peek()
        if tok is None:
            raise ExpressionError("fim inesperado da expressão")
        self.i += 1
        return tok

    def _expr(self) -> Node:
        node = self._term()
        while (tok := self._peek()) is not None and tok.text in ("+", "-"):
            self.i += 1
            node = BinOp(tok.text, node, self._term())
        return node

    def _term(self) -> Node:
        node = self._factor()
        while (tok := self._peek()) is not None and tok.text == "*":
            self.i += 1
            node = BinOp("*", node, self._factor())
        return node

    def _factor(self) -> Node:
        tok = self._take()
        if tok.kind == "int":
            return Num(int(tok.text))
        if tok.kind == "ident":
            return Attr(tok.text)
        if tok.kind == "dice":
            count_text, sides_text = tok.text.split("d")
            count = int(count_text) if count_text else 1
            sides = int(sides_text)
            if not 1 <= count <= MAX_DICE_COUNT:
                raise ExpressionError(
                    f"{tok.text}: quantidade de dados fora de 1..{MAX_DICE_COUNT}"
                )
            if not 2 <= sides <= MAX_DICE_SIDES:
                raise ExpressionError(f"{tok.text}: lados fora de 2..{MAX_DICE_SIDES}")
            return Dice(count, sides)
        if tok.text == "-":
            return Neg(self._factor())
        if tok.text == "(":
            node = self._expr()
            closing = self._peek()
            if closing is None or closing.text != ")":
                raise ExpressionError("parêntese sem fechar")
            self.i += 1
            return node
        raise ExpressionError(f"inesperado {tok.text!r} na posição {tok.pos}")


def parse(text: str) -> Node:
    """Converte texto em AST. Levanta ``ExpressionError`` em caso de sintaxe inválida."""
    return _Parser(text).parse()


def identifiers(node: Node) -> set[str]:
    """Nomes de atributos referenciados pela expressão."""
    if isinstance(node, Attr):
        return {node.name}
    if isinstance(node, Neg):
        return identifiers(node.operand)
    if isinstance(node, BinOp):
        return identifiers(node.left) | identifiers(node.right)
    return set()


# --- Avaliação -------------------------------------------------------------------


@dataclass(frozen=True)
class DiceRoll:
    """Um grupo de dados rolado, com os valores individuais (para narrar e auditar)."""

    dice: str  # "2d6"
    values: tuple[int, ...]

    @property
    def total(self) -> int:
        return sum(self.values)


@dataclass(frozen=True)
class EvalResult:
    total: int
    rolls: tuple[DiceRoll, ...]


def evaluate(node: Node, attributes: Mapping[str, int], rng: Rng) -> EvalResult:
    """Avalia a AST. Cada ``Dice`` consome ``count`` sorteios do ``rng``, da esquerda
    para a direita. Atributo ausente é ``ExpressionError``."""
    rolls: list[DiceRoll] = []

    def go(n: Node) -> int:
        if isinstance(n, Num):
            return n.value
        if isinstance(n, Attr):
            if n.name not in attributes:
                raise ExpressionError(f"atributo '{n.name}' não existe")
            return attributes[n.name]
        if isinstance(n, Dice):
            values = tuple(rng.roll(n.sides) for _ in range(n.count))
            rolls.append(DiceRoll(f"{n.count}d{n.sides}", values))
            return sum(values)
        if isinstance(n, Neg):
            return -go(n.operand)
        if n.op == "+":
            return go(n.left) + go(n.right)
        if n.op == "-":
            return go(n.left) - go(n.right)
        return go(n.left) * go(n.right)

    total = go(node)
    return EvalResult(total, tuple(rolls))


def roll(text: str, attributes: Mapping[str, int], rng: Rng) -> EvalResult:
    """Atalho: ``evaluate(parse(text), ...)``."""
    return evaluate(parse(text), attributes, rng)
