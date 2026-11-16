"""Avaliação da árvore com os atributos de um personagem e um gerador de números."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from devaneio.rng import Rng

from .errors import ExpressionError
from .nodes import Attr, Dice, Neg, Node, Num
from .parser import parse


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
