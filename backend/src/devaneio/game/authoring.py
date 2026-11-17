"""Validador de autoria: o que passa na validação mas quase certamente é engano do autor.

A validação (carga da campanha, do sistema e do pacote) recusa o que está quebrado. Aqui ficam os
achados em português que cruzam campanha, sistema e pacote: ``erro`` impede a campanha de funcionar
como o autor espera; ``aviso`` é um risco que ele pode aceitar de olhos abertos.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import ValidationError

from devaneio.narration import NarrationPack, lint_pack
from devaneio.rules import RuleSystem
from devaneio.schema import AtLocation, Campaign, CheckPassed, Condition, NpcDown


@dataclass(frozen=True)
class Finding:
    """Um achado da conferência de autoria: um erro ou um aviso, em português."""

    level: Literal["erro", "aviso"]
    text: str

    def __str__(self) -> str:
        return f"{self.level}: {self.text}"


def check_content(campaign: Campaign, rules: RuleSystem, pack: NarrationPack) -> list[Finding]:
    """Confere a campanha, o sistema de regras e a narração entre si; devolve os achados."""
    findings: list[Finding] = []
    skill_ids = {s.id for s in rules.skills}
    start = {n.id: n.location_id for n in campaign.npcs}

    def conditions_of(where: str, conditions: Sequence[Condition]) -> None:
        for cond in conditions:
            if isinstance(cond, CheckPassed) and cond.skill_id not in skill_ids:
                findings.append(
                    Finding(
                        "erro",
                        f"{where}: a habilidade '{cond.skill_id}' não existe no sistema "
                        f"'{rules.id}'; a condição nunca vale",
                    )
                )
            elif isinstance(cond, NpcDown) and _out_of_sight(cond.npc_id, start, conditions):
                findings.append(
                    Finding(
                        "aviso",
                        f"{where}: depende da queda de '{cond.npc_id}' sem exigir que o grupo "
                        f"esteja em '{start[cond.npc_id]}'; se ele cair longe do grupo, o evento "
                        "revela o nome dele",
                    )
                )

    for beat in campaign.beats:
        conditions_of(f"marco '{beat.id}', activate_when", beat.activate_when)
        conditions_of(f"marco '{beat.id}', complete_when", beat.complete_when)
    for fact in campaign.facts:
        conditions_of(f"fato '{fact.id}', reveal_when", fact.reveal_when)

    findings += [Finding("aviso", f"narração '{pack.id}': {w}") for w in lint_pack(pack)]
    return findings


def _out_of_sight(
    npc_id: str, start: dict[str, str | None], same_list: Sequence[Condition]
) -> bool:
    """O NPC começa num local e nada na mesma lista prende o gatilho a esse local."""
    location = start.get(npc_id)
    if location is None:
        return False
    return not any(isinstance(c, AtLocation) and c.location_id == location for c in same_list)


_CONDITION_KINDS = frozenset(
    {"at_location", "npc_down", "beat_done", "turn_at_least", "check_passed"}
)


def explain_validation_error(error: ValidationError) -> list[tuple[str, str]]:
    """Os erros de estrutura do Pydantic em português: ``(caminho, mensagem)``.

    O caminho é o do campo (``locations.2.connections.0``) e, sem o nome da variante de uma condição, é o
    mesmo que o autor vê no formulário. Um tipo de erro que não conhecemos vira uma frase genérica com o campo.
    """
    out: list[tuple[str, str]] = []
    for item in error.errors():
        loc = _clean_loc(item["loc"])
        field = str(loc[-1]) if loc else "a campanha"
        out.append((".".join(str(p) for p in loc), _explain(item["type"], field, item)))
    return out


def _clean_loc(loc: tuple[int | str, ...]) -> list[int | str]:
    """O caminho sem o nome da variante de condição que o Pydantic põe antes do campo."""
    cleaned: list[int | str] = []
    for index, part in enumerate(loc):
        if (
            isinstance(part, str)
            and part in _CONDITION_KINDS
            and index > 0
            and isinstance(loc[index - 1], int)
        ):
            continue
        cleaned.append(part)
    return cleaned


def _explain(kind: str, field: str, item: Any) -> str:
    ctx = item.get("ctx") or {}
    if kind == "missing":
        return f"falta preencher '{field}'"
    if kind == "extra_forbidden":
        return f"'{field}' não é um campo conhecido"
    if kind == "string_pattern_mismatch":
        return (
            f"'{field}' só pode ter letras minúsculas sem acento, números, '-' e '_', "
            "começando por letra ou número"
        )
    if kind in {"string_too_short", "too_short"}:
        return f"'{field}' não pode ficar vazio"
    if kind in {"string_too_long", "too_long"}:
        return f"'{field}' passa do tamanho máximo"
    if kind in {"string_type", "string_unicode"}:
        return f"'{field}' precisa ser um texto"
    if kind in {"int_type", "int_parsing", "int_from_float"}:
        return f"'{field}' precisa ser um número inteiro"
    if kind in {"bool_type", "bool_parsing"}:
        return f"'{field}' precisa ser sim ou não"
    if kind == "list_type":
        return f"'{field}' precisa ser uma lista"
    if kind in {"dict_type", "model_type", "model_attributes_type"}:
        return f"'{field}' precisa ser um bloco de campos"
    if kind in {"greater_than_equal", "greater_than"}:
        return f"'{field}' precisa ser pelo menos {ctx.get('ge', ctx.get('gt', 0))}"
    if kind in {"less_than_equal", "less_than"}:
        return f"'{field}' precisa ser no máximo {ctx.get('le', ctx.get('lt', 0))}"
    if kind in {"literal_error", "enum"}:
        return f"'{field}' tem um valor que não é aceito"
    if kind in {"union_tag_invalid", "union_tag_not_found"}:
        return f"'{field}': tipo de condição desconhecido"
    return f"'{field}' não está certo"
