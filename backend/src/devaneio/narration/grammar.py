"""Gramática de expansão no estilo Tracery.

Regras: ``{"simbolo": ["alternativa com #outro# e #variavel#", ...]}``. Expandir um símbolo
escolhe uma alternativa com o ``Rng`` dado e substitui cada ``#nome#`` por uma variável
(valor fixo fornecido na chamada) ou pela expansão recursiva de outra regra. Nada de código
nos templates: só texto e referências.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from devaneio.rng import Rng

MAX_DEPTH = 24
_REF = re.compile(r"#([A-Za-z0-9_.\-]+)#")


class GrammarError(ValueError):
    """Símbolo indefinido, regra vazia ou recursão sem fim."""


def referenced_symbols(template: str) -> list[str]:
    """Nomes referenciados como ``#nome#`` num template, na ordem, com repetições."""
    return _REF.findall(template)


class Grammar:
    def __init__(self, rules: Mapping[str, Sequence[str]]) -> None:
        for symbol, options in rules.items():
            if not options:
                raise GrammarError(f"regra '{symbol}' não tem alternativas")
        self.rules: dict[str, tuple[str, ...]] = {k: tuple(v) for k, v in rules.items()}

    def undefined(self, variables: Mapping[str, Sequence[str]] | None = None) -> list[str]:
        """Referências que não são regra nem variável permitida, como ``"raiz: #ref#"``.

        ``variables`` mapeia regra-raiz -> variáveis que ela (e tudo que ela alcança) pode
        usar. Sem o mapa, toda regra é raiz sem variáveis. Regras que nenhuma raiz alcança
        são conferidas sem variáveis.
        """
        roots: dict[str, set[str]] = (
            {k: set(v) for k, v in variables.items()}
            if variables
            else {k: set() for k in self.rules}
        )
        problems: set[str] = set()
        reached: set[str] = set()
        for root, allowed in roots.items():
            if root not in self.rules:
                continue
            refs, visited = self._closure(root)
            reached |= visited
            problems |= {
                f"{root}: #{ref}#" for ref in refs if ref not in self.rules and ref not in allowed
            }
        for orphan in set(self.rules) - reached:
            refs, _ = self._closure(orphan)
            problems |= {f"{orphan}: #{ref}#" for ref in refs if ref not in self.rules}
        return sorted(problems)

    def _closure(self, root: str) -> tuple[set[str], set[str]]:
        """(referências alcançáveis a partir de root, regras visitadas)."""
        visited: set[str] = set()
        stack = [root]
        refs: set[str] = set()
        while stack:
            symbol = stack.pop()
            if symbol in visited or symbol not in self.rules:
                continue
            visited.add(symbol)
            for option in self.rules[symbol]:
                for ref in referenced_symbols(option):
                    refs.add(ref)
                    if ref in self.rules:
                        stack.append(ref)
        return refs, visited

    def expand(self, symbol: str, variables: Mapping[str, str], rng: Rng) -> str:
        return self._expand(symbol, variables, rng, 0)

    def _expand(self, symbol: str, variables: Mapping[str, str], rng: Rng, depth: int) -> str:
        if depth > MAX_DEPTH:
            raise GrammarError(f"recursão profunda demais ao expandir '{symbol}'")
        if symbol in variables:
            return variables[symbol]
        options = self.rules.get(symbol)
        if options is None:
            raise GrammarError(f"símbolo '{symbol}' não é regra nem variável")
        chosen = options[rng.roll(len(options)) - 1]

        def sub(match: re.Match[str]) -> str:
            return self._expand(match.group(1), variables, rng, depth + 1)

        return _REF.sub(sub, chosen)
