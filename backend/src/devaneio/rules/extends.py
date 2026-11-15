"""``extends`` de sistemas de regras: um arquivo declara só o que muda em relação a um pai.

Um nível, sem cadeia: o pai é um sistema completo (embutido ou de arquivo sem ``extends``). A
mescla acontece sobre dicts, antes da validação, e o resultado passa pela validação de sempre
(``RuleSystem`` mais ``validate_rules``), então um sistema estendido é tão checado quanto um completo.
"""

from __future__ import annotations

import copy
import json
from collections import Counter
from collections.abc import Callable
from typing import Any, Literal

from pydantic import model_validator

from devaneio.schema.common import Id, StrictModel

from .schema import (
    Attribute,
    Difficulty,
    Formula,
    Modifier,
    RuleSystem,
    Skill,
    Weapon,
)
from .validation import builtin_rules_json, load_rules

LIST_KEYS = ("attributes", "difficulties", "skills", "weapons", "modifiers")
BLOCK_KEYS = ("outcomes", "combat", "dispositions", "rest")


class RulesExtendsError(ValueError):
    """``extends`` mal usado (pai inexistente, cadeia, id repetido)."""


class OutcomesPatch(StrictModel):
    critical_failure_margin: int | None = None
    critical_success_margin: int | None = None


class CombatPatch(StrictModel):
    attack_difficulty: Id | None = None
    default_weapon: Id | None = None
    fallen_can_act: bool | None = None


class DispositionsPatch(StrictModel):
    hostile_below: int | None = None


class RestPatch(StrictModel):
    heal: Formula | None = None


class RuleSystemExtension(StrictModel):
    """Arquivo de sistema que estende outro. Só ``id`` e ``extends`` são obrigatórios. Item de
    lista com o id de um item do pai o substitui por inteiro; id novo é acrescentado. Blocos
    mudam campo a campo; ``default_weapon: null`` explícito limpa a arma padrão do pai."""

    schema_version: Literal[1] = 1
    id: Id
    extends: Id
    name: str | None = None
    description: str | None = None
    attributes: list[Attribute] | None = None
    difficulties: list[Difficulty] | None = None
    skills: list[Skill] | None = None
    weapons: list[Weapon] | None = None
    modifiers: list[Modifier] | None = None
    outcomes: OutcomesPatch | None = None
    combat: CombatPatch | None = None
    dispositions: DispositionsPatch | None = None
    rest: RestPatch | None = None
    max_hp: Formula | None = None

    @model_validator(mode="after")
    def _explicit_values_are_usable(self) -> RuleSystemExtension:
        """``null`` explícito não significa "herdar" (omitir é que herda); só ``default_weapon``,
        dentro de ``combat``, usa ``null`` para limpar. Id repetido numa lista do filho seria um
        item perdido em silêncio na mescla."""
        errors = [
            f"'{name}' não pode ser null (omita o campo para herdar do pai)"
            for name in self.model_fields_set
            if getattr(self, name) is None
        ]
        for key in LIST_KEYS:
            counts = Counter(item.id for item in getattr(self, key) or [])
            errors += [f"{key}: id repetido '{i}' ({n} vezes)" for i, n in counts.items() if n > 1]
        if errors:
            raise ValueError("; ".join(errors))
        return self


def merge_rules(parent: dict[str, Any], extension: dict[str, Any]) -> dict[str, Any]:
    """Pai mais as chaves declaradas no filho (``extends`` não entra no resultado). Não muta."""
    merged = copy.deepcopy(parent)
    for key, value in extension.items():
        if key == "extends":
            continue
        if key in LIST_KEYS:
            merged[key] = _merge_by_id(merged.get(key, []), value)
        elif key in BLOCK_KEYS:
            merged[key] = {**merged.get(key, {}), **value}
        else:
            merged[key] = value
    return merged


def _merge_by_id(parent: list[dict[str, Any]], child: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = list(parent)
    positions = {item["id"]: i for i, item in enumerate(result)}
    for item in child:
        if item["id"] in positions:
            result[positions[item["id"]]] = item
        else:
            positions[item["id"]] = len(result)
            result.append(item)
    return result


def builtin_rules_dict(rules_id: str) -> dict[str, Any]:
    """O sistema embutido como dict (para ser pai de um ``extends``)."""
    parsed: dict[str, Any] = json.loads(builtin_rules_json(rules_id))
    return parsed


def load_rules_extending(data: Any, load_parent: Callable[[str], dict[str, Any]]) -> RuleSystem:
    """Carrega um sistema, resolvendo ``extends`` por ``load_parent`` (id -> dict do pai, que
    levanta ``ValueError`` se não existe). Sem ``extends``, é um ``load_rules`` comum."""
    raw = json.loads(data) if isinstance(data, (str, bytes, bytearray)) else data
    if not isinstance(raw, dict) or "extends" not in raw:
        return load_rules(raw)
    extension = RuleSystemExtension.model_validate(raw)
    if extension.id == extension.extends:
        raise RulesExtendsError(f"sistema '{extension.id}' não pode estender a si mesmo")
    parent = load_parent(extension.extends)
    if "extends" in parent:
        raise RulesExtendsError(
            f"'{extension.extends}' já estende outro sistema; só um nível de extends é permitido"
        )
    if parent.get("id") == extension.id:
        raise RulesExtendsError(f"'{extension.id}' repete o id do sistema pai")
    return load_rules(merge_rules(parent, extension.model_dump(mode="json", exclude_unset=True)))
