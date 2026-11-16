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

from .errors import ExpressionError
from .evaluate import DiceRoll, EvalResult, evaluate, roll
from .nodes import Attr, BinOp, Dice, Neg, Node, Num, identifiers
from .parser import MAX_DICE_COUNT, MAX_DICE_SIDES, parse

__all__ = [
    "MAX_DICE_COUNT",
    "MAX_DICE_SIDES",
    "Attr",
    "BinOp",
    "Dice",
    "DiceRoll",
    "EvalResult",
    "ExpressionError",
    "Neg",
    "Node",
    "Num",
    "evaluate",
    "identifiers",
    "parse",
    "roll",
]
