"""Narração por templates e gramáticas (sem LLM). Gerada na exibição, nunca gravada no estado."""

from .grammar import Grammar, GrammarError, referenced_symbols

__all__ = ["Grammar", "GrammarError", "referenced_symbols"]
