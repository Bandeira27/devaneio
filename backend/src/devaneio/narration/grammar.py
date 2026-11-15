"""Gramática de expansão no estilo Tracery.

Regras: ``{"simbolo": ["alternativa com #outro# e #variavel#", ...]}``. Expandir um símbolo
escolhe uma alternativa com o ``Rng`` dado e substitui cada ``#nome#`` por uma variável
(valor fixo fornecido na chamada) ou pela expansão recursiva de outra regra. Nada de código
nos templates: só texto e referências.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Iterable, Mapping, Sequence

from devaneio.rng import Rng

MAX_DEPTH = 24
# Limites contra pacote do autor que explode ao expandir (cada regra se refere três vezes à
# próxima, 3^n): o pior caso é conferido na carga e as expansões são contadas ao narrar.
MAX_EXPANSIONS = 500
MAX_EXPANDED_CHARS = 2000
VARIABLE_CHARS = 100  # tamanho presumido de uma variável (nome, local...) no pior caso
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

    def cycles(self) -> list[str]:
        """Ciclos entre regras, cada um como ``a -> b -> a`` (uma vez por ciclo achado)."""
        found: list[str] = []
        state: dict[str, int] = {}  # 1 = no caminho atual, 2 = concluída
        path: list[str] = []

        def visit(symbol: str) -> None:
            state[symbol] = 1
            path.append(symbol)
            for ref in sorted(self._refs(symbol)):
                if ref not in self.rules:
                    continue
                if state.get(ref) == 1:
                    found.append(" -> ".join([*path[path.index(ref) :], ref]))
                elif ref not in state:
                    visit(ref)
            path.pop()
            state[symbol] = 2

        for symbol in self.rules:
            if symbol not in state:
                visit(symbol)
        return found

    def worst_length(self, symbol: str, variables: Collection[str]) -> int:
        """Maior texto possível ao expandir ``symbol`` (variável conta ``VARIABLE_CHARS``). Só vale
        sem ciclos: confira ``cycles()`` antes."""
        memo: dict[str, int] = {}

        def worst(name: str) -> int:
            if name in memo:
                return memo[name]
            best = 0
            for option in self.rules[name]:
                total = len(_REF.sub("", option))
                for ref in referenced_symbols(option):
                    if ref in self.rules:
                        total += worst(ref)
                    elif ref in variables:
                        total += VARIABLE_CHARS
                best = max(best, total)
            memo[name] = best
            return best

        return worst(symbol)

    def _refs(self, symbol: str) -> set[str]:
        return {ref for option in self.rules[symbol] for ref in referenced_symbols(option)}

    def reachable(self, roots: Iterable[str]) -> set[str]:
        """Regras alcançáveis a partir das ``roots`` (elas incluídas, as que existem)."""
        visited: set[str] = set()
        for root in roots:
            visited |= self._closure(root)[1]
        return visited

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
        return self._expand(symbol, variables, rng, 0, [MAX_EXPANSIONS])

    def _expand(
        self, symbol: str, variables: Mapping[str, str], rng: Rng, depth: int, budget: list[int]
    ) -> str:
        budget[0] -= 1
        if budget[0] < 0:
            raise GrammarError(
                f"expansão grande demais em '{symbol}' (mais de {MAX_EXPANSIONS} passos)"
            )
        if depth > MAX_DEPTH:
            raise GrammarError(f"recursão profunda demais ao expandir '{symbol}'")
        if symbol in variables:
            return variables[symbol]
        options = self.rules.get(symbol)
        if options is None:
            raise GrammarError(f"símbolo '{symbol}' não é regra nem variável")
        chosen = options[rng.roll(len(options)) - 1]

        def sub(match: re.Match[str]) -> str:
            return self._expand(match.group(1), variables, rng, depth + 1, budget)

        return _REF.sub(sub, chosen)
