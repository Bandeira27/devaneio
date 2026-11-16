"""Árvore sintática das expressões e a leitura dos atributos que ela cita."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Num:
    """Um número literal."""

    value: int


@dataclass(frozen=True)
class Dice:
    """Um grupo de dados: `count` dados de `sides` lados."""

    count: int
    sides: int


@dataclass(frozen=True)
class Attr:
    """Um atributo do personagem, pelo id."""

    name: str


@dataclass(frozen=True)
class Neg:
    """A negação de uma expressão."""

    operand: Node


@dataclass(frozen=True)
class BinOp:
    """Uma conta de dois lados: soma, subtração ou multiplicação."""

    op: str  # "+", "-", "*"
    left: Node
    right: Node


Node = Num | Dice | Attr | Neg | BinOp


def identifiers(node: Node) -> set[str]:
    """Nomes de atributos referenciados pela expressão."""
    if isinstance(node, Attr):
        return {node.name}
    if isinstance(node, Neg):
        return identifiers(node.operand)
    if isinstance(node, BinOp):
        return identifiers(node.left) | identifiers(node.right)
    return set()
