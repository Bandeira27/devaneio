"""Integridade de um sistema de regras e coerência do estado com ele."""

from __future__ import annotations

from collections import Counter
from importlib import resources
from typing import Any, Iterable

from devaneio.schema.game_state import GameState

from .expression import identifiers, parse
from .schema import RuleSystem


class RulesIntegrityError(ValueError):
    """Sistema estruturalmente válido, mas incoerente. ``errors`` tem a lista completa."""

    def __init__(self, errors: Iterable[str]) -> None:
        self.errors = list(errors)
        super().__init__(
            "Sistema de regras inconsistente:\n" + "\n".join(f"- {e}" for e in self.errors)
        )


def validate_rules(rules: RuleSystem) -> list[str]:
    """Lista vazia significa sistema coerente."""
    errors: list[str] = []
    errors += _duplicates("attributes", (x.id for x in rules.attributes))
    errors += _duplicates("difficulties", (x.id for x in rules.difficulties))
    errors += _duplicates("skills", (x.id for x in rules.skills))
    errors += _duplicates("weapons", (x.id for x in rules.weapons))
    errors += _duplicates("modifiers", (x.id for x in rules.modifiers))

    attr_ids = {x.id for x in rules.attributes}

    def check_formula(where: str, formula: str) -> None:
        for name in sorted(identifiers(parse(formula)) - attr_ids):
            errors.append(f"{where}: fórmula usa atributo '{name}', que não existe")

    for skill in rules.skills:
        check_formula(f"skill '{skill.id}'", skill.formula)
    for weapon in rules.weapons:
        check_formula(f"weapon '{weapon.id}'", weapon.damage)
    check_formula("max_hp", rules.max_hp)
    return errors


def load_rules(data: Any) -> RuleSystem:
    """Valida estrutura (Pydantic) e integridade. ``data`` é JSON (str/bytes) ou dict."""
    if isinstance(data, (str, bytes, bytearray)):
        rules = RuleSystem.model_validate_json(data)
    else:
        rules = RuleSystem.model_validate(data)
    errors = validate_rules(rules)
    if errors:
        raise RulesIntegrityError(errors)
    return rules


def builtin_rules_json(rules_id: str) -> str:
    """Texto JSON de um sistema distribuído com o pacote (``rules/data/<id>.json``)."""
    resource = resources.files("devaneio.rules").joinpath(f"data/{rules_id}.json")
    if not resource.is_file():
        raise ValueError(f"sistema de regras '{rules_id}' não encontrado")
    return resource.read_text(encoding="utf-8")


def load_builtin_rules(rules_id: str = "default") -> RuleSystem:
    return load_rules(builtin_rules_json(rules_id))


def validate_state_against_rules(state: GameState, rules: RuleSystem) -> list[str]:
    """Todo personagem tem exatamente os atributos declarados, dentro dos limites."""
    errors: list[str] = []
    declared = {a.id: a for a in rules.attributes}
    for char_id, char in state.characters.items():
        for name in sorted(set(declared) - set(char.attributes)):
            errors.append(f"personagem '{char_id}' não tem o atributo '{name}'")
        for name in sorted(set(char.attributes) - set(declared)):
            errors.append(f"personagem '{char_id}' tem atributo '{name}', que o sistema não declara")
        for name, value in char.attributes.items():
            attr = declared.get(name)
            if attr is not None and not attr.min <= value <= attr.max:
                errors.append(
                    f"personagem '{char_id}': {name} = {value} fora de [{attr.min}, {attr.max}]"
                )
    return errors


def _duplicates(collection: str, ids: Iterable[str]) -> list[str]:
    counts = Counter(ids)
    return [f"{collection}: id duplicado '{i}' ({n} vezes)" for i, n in counts.items() if n > 1]


__all__ = [
    "RulesIntegrityError",
    "builtin_rules_json",
    "load_builtin_rules",
    "load_rules",
    "validate_rules",
    "validate_state_against_rules",
]

