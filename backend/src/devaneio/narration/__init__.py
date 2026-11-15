"""Narração por templates e gramáticas (sem LLM). Gerada na exibição, nunca gravada no estado."""

from .extends import (
    NarrationPackExtension,
    PackExtendsError,
    builtin_pack_dict,
    load_pack_extending,
    merge_pack,
)
from .grammar import Grammar, GrammarError, referenced_symbols
from .lint import lint_pack
from .narrator import Narrator
from .pack import (
    EVENT_VARIABLES,
    EVENT_VARIANTS,
    NarrationIntegrityError,
    NarrationPack,
    builtin_pack_json,
    load_builtin_pack,
    load_pack,
    validate_pack,
)

__all__ = [
    "EVENT_VARIABLES",
    "EVENT_VARIANTS",
    "Grammar",
    "GrammarError",
    "NarrationIntegrityError",
    "NarrationPack",
    "NarrationPackExtension",
    "Narrator",
    "PackExtendsError",
    "builtin_pack_dict",
    "builtin_pack_json",
    "lint_pack",
    "load_builtin_pack",
    "load_pack",
    "load_pack_extending",
    "merge_pack",
    "referenced_symbols",
    "validate_pack",
]
