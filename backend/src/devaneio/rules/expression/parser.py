"""Parser de descida recursiva: transforma os tokens em árvore, validando os limites dos dados."""

from __future__ import annotations

from .errors import ExpressionError
from .nodes import Attr, BinOp, Dice, Neg, Node, Num
from .tokens import Token, tokenize

MAX_DICE_COUNT = 100
MAX_DICE_SIDES = 1000


class Parser:
    """Parser de descida recursiva de uma expressão (veja a gramática no pacote)."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.tokens = tokenize(text)
        self.i = 0

    def parse(self) -> Node:
        """Lê a expressão inteira; sobra de texto é erro."""
        if not self.tokens:
            raise ExpressionError("expressão vazia")
        node = self._expr()
        if self.i < len(self.tokens):
            tok = self.tokens[self.i]
            raise ExpressionError(f"sobrou {tok.text!r} na posição {tok.pos}")
        return node

    def _peek(self) -> Token | None:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def _take(self) -> Token:
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
    return Parser(text).parse()
