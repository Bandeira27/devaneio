"""Árvore sintática das expressões e a leitura dos atributos que ela cita."""

from __future__ import annotations

from dataclasses import dataclass


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


def identifiers(node: Node) -> set[str]:
    """Nomes de atributos referenciados pela expressão."""
    if isinstance(node, Attr):
        return {node.name}
    if isinstance(node, Neg):
        return identifiers(node.operand)
    if isinstance(node, BinOp):
        return identifiers(node.left) | identifiers(node.right)
    return set()
