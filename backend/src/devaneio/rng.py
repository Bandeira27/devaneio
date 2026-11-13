"""Gerador de números aleatórios reprodutível.

O estado guarda só ``rng_seed`` e ``rng_draws``; recriar ``Rng(seed, draws)`` reproduz
exatamente a sequência a partir daquele ponto. Implementação própria (SplitMix64) em vez de
``random.Random``: determinística entre versões do Python e portável para TypeScript.
"""

from __future__ import annotations

_MASK = (1 << 64) - 1


class Rng:
    def __init__(self, seed: int, draws: int = 0) -> None:
        if draws < 0:
            raise ValueError("draws não pode ser negativo")
        self.seed = seed
        self._state = seed & _MASK
        self.draws = 0
        for _ in range(draws):
            self._next()

    def _next(self) -> int:
        """Próximo valor de 64 bits (SplitMix64)."""
        self._state = (self._state + 0x9E3779B97F4A7C15) & _MASK
        z = self._state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _MASK
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _MASK
        self.draws += 1
        return z ^ (z >> 31)

    def roll(self, sides: int) -> int:
        """Inteiro uniforme em [1, sides]. Um sorteio por chamada.

        Usa módulo: para dados de até milhares de lados o viés é da ordem de 2**-64.
        """
        if sides < 1:
            raise ValueError("um dado precisa de pelo menos 1 lado")
        return self._next() % sides + 1
