"""Integridade de um sistema de regras e coerência do estado com ele."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from importlib import resources
from typing import Any

from devaneio.schema.campaign import Campaign
from devaneio.schema.game_state import GameState

from .expression import identifiers, parse
from .schema import Attribute, RuleSystem


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
    skill_ids = {x.id for x in rules.skills}
    for weapon in rules.weapons:
        check_formula(f"weapon '{weapon.id}'", weapon.damage)
        if weapon.skill not in skill_ids:
            errors.append(f"weapon '{weapon.id}': habilidade '{weapon.skill}' não existe")
    check_formula("max_hp", rules.max_hp)
    check_formula("rest.heal", rules.rest.heal)

    if rules.combat.attack_difficulty not in {x.id for x in rules.difficulties}:
        errors.append(f"combat.attack_difficulty '{rules.combat.attack_difficulty}' não existe")
    weapon_ids = {x.id for x in rules.weapons}
    if rules.combat.default_weapon is not None and rules.combat.default_weapon not in weapon_ids:
        errors.append(f"combat.default_weapon '{rules.combat.default_weapon}' não existe")
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


def validate_campaign_against_rules(campaign: Campaign, rules: RuleSystem) -> list[str]:
    """A campanha pede este sistema e os atributos parciais dos NPCs existem nele."""
    errors: list[str] = []
    if campaign.rules_id != rules.id:
        errors.append(
            f"campanha pede o sistema '{campaign.rules_id}', mas o sistema é '{rules.id}'"
        )
    declared = {a.id: a for a in rules.attributes}
    weapon_ids = {w.id for w in rules.weapons}
    for npc in campaign.npcs:
        errors += _attribute_errors(f"npc '{npc.id}'", npc.attributes, declared, partial=True)
        if npc.weapon_id is not None and npc.weapon_id not in weapon_ids:
            errors.append(f"npc '{npc.id}': arma '{npc.weapon_id}' não existe no sistema")
        elif npc.weapon_id is None and rules.combat.default_weapon is None:
            errors.append(
                f"npc '{npc.id}' não tem arma e o sistema não define combat.default_weapon"
            )
    return errors


def validate_state_against_rules(state: GameState, rules: RuleSystem) -> list[str]:
    """Personagens e NPCs têm exatamente os atributos declarados, dentro dos limites."""
    errors: list[str] = []
    declared = {a.id: a for a in rules.attributes}
    for char_id, char in state.characters.items():
        errors += _attribute_errors(f"personagem '{char_id}'", char.attributes, declared)
    for npc_id, npc in state.npcs.items():
        errors += _attribute_errors(f"npc '{npc_id}'", npc.attributes, declared)
    return errors


def _attribute_errors(
    who: str, attributes: dict[str, int], declared: dict[str, Attribute], partial: bool = False
) -> list[str]:
    errors: list[str] = []
    if not partial:
        for name in sorted(set(declared) - set(attributes)):
            errors.append(f"{who} não tem o atributo '{name}'")
    for name in sorted(set(attributes) - set(declared)):
        errors.append(f"{who} tem atributo '{name}', que o sistema não declara")
    for name, value in attributes.items():
        attr = declared.get(name)
        if attr is not None and not attr.min <= value <= attr.max:
            errors.append(f"{who}: {name} = {value} fora de [{attr.min}, {attr.max}]")
    return errors


def _duplicates(collection: str, ids: Iterable[str]) -> list[str]:
    counts = Counter(ids)
    return [f"{collection}: id duplicado '{i}' ({n} vezes)" for i, n in counts.items() if n > 1]


__all__ = [
    "RulesIntegrityError",
    "builtin_rules_json",
    "load_builtin_rules",
    "load_rules",
    "validate_campaign_against_rules",
    "validate_rules",
    "validate_state_against_rules",
]
