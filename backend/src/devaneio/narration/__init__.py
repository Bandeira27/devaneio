"""Narração por templates e gramáticas (sem LLM). Gerada na exibição, nunca gravada no estado."""

from .grammar import Grammar, GrammarError, referenced_symbols
from .narrator import Narrator
from .pack import (
    EVENT_VARIABLES,
    NarrationIntegrityError,
    NarrationPack,
    builtin_pack_json,
    load_builtin_pack,
    load_pack,
    validate_pack,
)

__all__ = [
    "EVENT_VARIABLES",
    "Grammar",
    "GrammarError",
    "NarrationIntegrityError",
    "NarrationPack",
    "Narrator",
    "builtin_pack_json",
    "load_builtin_pack",
    "load_pack",
    "referenced_symbols",
    "validate_pack",
]
