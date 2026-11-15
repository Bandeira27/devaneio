"""Texto que vem do LLM e chega à tela de alguém: sem caracteres que enganam ou sujam.

ESC/ANSI, bidi, zero-width e separadores de linha passam por qualquer modelo e, na prosa e
na fala, chegariam a outros jogadores (impersonação, terminal). Removê-los é barato e não
muda texto legítimo.
"""

from __future__ import annotations

import unicodedata

_UNSAFE = {"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"}


def clean_text(text: str) -> str:
    """Espaço em branco de qualquer tipo (inclusive quebra de linha e tab) vira um espaço só;
    controle, formatação e substitutos somem. A ordem importa: "a\\nb" tem de continuar "a b"."""
    kept = "".join(
        " " if ch.isspace() else ch
        for ch in text
        if ch.isspace() or unicodedata.category(ch) not in _UNSAFE
    )
    return " ".join(kept.split())
