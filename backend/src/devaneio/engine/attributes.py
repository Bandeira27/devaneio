"""Atributos parciais (campanha ou jogador) completados e conferidos contra o sistema."""

from __future__ import annotations

from collections.abc import Mapping

from devaneio.rules import RuleSystem

from .errors import EngineError


def resolve_attributes(rules: RuleSystem, partial: Mapping[str, int], who: str) -> dict[str, int]:
    """Preenche ausentes com o default do sistema; chave desconhecida ou valor fora de
    [min, max] é ``EngineError`` com todos os problemas de uma vez."""
    declared = {a.id: a for a in rules.attributes}
    errors = [f"atributo '{k}' não existe no sistema" for k in sorted(set(partial) - set(declared))]
    for name, value in partial.items():
        attr = declared.get(name)
        if attr is not None and not attr.min <= value <= attr.max:
            errors.append(f"{name} = {value} fora de [{attr.min}, {attr.max}]")
    if errors:
        raise EngineError(f"{who}: " + "; ".join(errors))
    return {a.id: partial.get(a.id, a.default) for a in rules.attributes}
