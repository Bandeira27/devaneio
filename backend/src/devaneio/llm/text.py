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


def clean_multiline(text: str, limit: int) -> str:
    """Como ``clean_text``, mas mantém as quebras de linha (resposta longa para o anfitrião).
    Controle, formatação e substitutos somem; tab e espaços repetidos viram um espaço; mais de uma
    linha em branco seguida vira uma; corta em ``limit`` caracteres."""
    lines: list[str] = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        kept = "".join(
            " " if ch.isspace() else ch
            for ch in line
            if ch.isspace() or unicodedata.category(ch) not in _UNSAFE
        )
        lines.append(" ".join(kept.split()))
    result: list[str] = []
    for line in lines:
        if line or (result and result[-1]):
            result.append(line)
    return "\n".join(result).strip()[:limit]
