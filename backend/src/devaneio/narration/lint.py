"""Avisos de autoria de um pacote de narração: o que passa na validação mas quase certamente é engano.

A validação (``validate_pack``) recusa o que quebra a gramática. Aqui ficam os avisos: chave com
tipo de evento ou variante que o narrador não usa (a regra nunca dispara), tipo de evento sem
regra (o jogador vê o texto mecânico) e regra auxiliar que nenhuma regra de evento alcança.
"""

from __future__ import annotations

from .grammar import Grammar
from .pack import EVENT_VARIABLES, EVENT_VARIANTS, NarrationPack


def lint_pack(pack: NarrationPack) -> list[str]:
    """Avisos sobre um pacote de narração: chaves desconhecidas, regras sem uso e tipos sem regra."""
    warnings: list[str] = []
    event_roots: list[str] = []
    for key in pack.rules:
        kind, _, variant = key.partition(".")
        if kind in EVENT_VARIABLES:
            event_roots.append(key)
            allowed = EVENT_VARIANTS.get(kind, ())
            if variant and variant not in allowed:
                shown = ", ".join(allowed) or "nenhuma"
                warnings.append(
                    f"regra '{key}': o narrador não usa a variante '{variant}' de '{kind}' "
                    f"(variantes: {shown}); ela nunca dispara"
                )
        elif variant:
            warnings.append(
                f"regra '{key}': '{kind}' não é um tipo de evento "
                f"({', '.join(sorted(EVENT_VARIABLES))}); ela nunca dispara"
            )
    reached = Grammar(pack.rules).reachable(event_roots)
    for key in pack.rules:
        kind, _, variant = key.partition(".")
        if kind not in EVENT_VARIABLES and not variant and key not in reached:
            warnings.append(f"regra auxiliar '{key}': nenhuma regra de evento a usa")
    covered = {key.partition(".")[0] for key in pack.rules}
    for kind in EVENT_VARIABLES:
        if kind not in covered:
            warnings.append(
                f"não há regra para o evento '{kind}': o jogador verá o texto mecânico dele"
            )
    return warnings
