"""Validador de autoria: o que passa na validação mas quase certamente é engano do autor.

A validação (carga da campanha, do sistema e do pacote) recusa o que está quebrado. Aqui ficam os
achados em português que cruzam campanha, sistema e pacote: ``erro`` impede a campanha de funcionar
como o autor espera; ``aviso`` é um risco que ele pode aceitar de olhos abertos.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, get_args

from pydantic import ValidationError

from devaneio.narration import NarrationPack, lint_pack
from devaneio.rules import RuleSystem, validate_campaign_against_rules
from devaneio.schema import (
    AtLocation,
    Campaign,
    CampaignIntegrityError,
    CheckPassed,
    Condition,
    NpcDown,
    load_campaign,
)

from .content import load_pack_for, load_rules_for
from .errors import GameError


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


@dataclass(frozen=True)
class CampaignCheck:
    """O resultado de conferir uma campanha ainda não gravada.

    ``errors`` são ``(caminho do campo, frase)``; só com ``errors`` vazio há ``campaign`` e ``rules``.
    ``findings`` são os achados de autoria.
    """

    errors: list[tuple[str, str]]
    findings: list[Finding]
    campaign: Campaign | None = None
    rules: RuleSystem | None = None


def check_campaign_data(data: Any, campaign_dir: Path) -> CampaignCheck:
    """Confere uma campanha (JSON cru) como o jogo a conferiria ao carregar, com tudo em português.

    Estrutura (Pydantic), integridade, o sistema e a narração que ela cita (procurados ao lado de
    ``campaign_dir``) e, por fim, os achados de autoria. Nunca levanta por causa do conteúdo.
    """
    try:
        campaign = load_campaign(data)
    except ValidationError as exc:
        return CampaignCheck(explain_validation_error(exc), [])
    except CampaignIntegrityError as exc:
        return CampaignCheck([("", message) for message in exc.errors], [])
    try:
        rules = load_rules_for(campaign, campaign_dir)
        pack = load_pack_for(campaign, campaign_dir)
    except GameError as exc:
        return CampaignCheck([("", str(exc))], [])
    errors = [("", message) for message in validate_campaign_against_rules(campaign, rules)]
    findings = check_content(campaign, rules, pack)
    if errors:
        return CampaignCheck(errors, findings)
    return CampaignCheck([], findings, campaign, rules)


# Os nomes das variantes de ``Condition``: o Pydantic os põe no caminho do erro, e o autor não os vê.
_CONDITION_KINDS = frozenset(
    get_args(model.model_fields["kind"].annotation)[0] for model in get_args(get_args(Condition)[0])
)


def explain_validation_error(error: ValidationError) -> list[tuple[str, str]]:
    """Os erros de estrutura do Pydantic em português: ``(caminho, mensagem)``.

    O caminho é o do campo (``locations.2.connections.0``), sem o nome da variante de uma condição. O campo
    citado na frase é o último nome do caminho; num item de lista, ``item N de <lista>``.
    """
    out: list[tuple[str, str]] = []
    for item in error.errors():
        loc = _clean_loc(item["loc"])
        out.append((".".join(str(p) for p in loc), _explain(item, _field_name(loc))))
    return out


def _clean_loc(loc: tuple[int | str, ...]) -> list[int | str]:
    """O caminho sem o nome da variante de condição que o Pydantic põe antes do campo."""
    return [
        part
        for index, part in enumerate(loc)
        if not (
            isinstance(part, str)
            and part in _CONDITION_KINDS
            and index > 0
            and isinstance(loc[index - 1], int)
        )
    ]


def _field_name(loc: list[int | str]) -> str:
    """Como a frase chama o campo: o nome, ou ``item N de <lista>`` quando o erro é num item de lista."""
    if not loc:
        return "a campanha"
    last = loc[-1]
    if isinstance(last, int):
        names = [p for p in loc if isinstance(p, str)]
        return f"item {last + 1} de '{names[-1]}'" if names else f"item {last + 1}"
    return f"'{last}'"


def _explain(item: Any, field: str) -> str:
    kind = item["type"]
    ctx = item.get("ctx") or {}
    if kind == "missing":
        return f"falta preencher {field}"
    if kind == "extra_forbidden":
        return f"{field} não é um campo conhecido"
    if kind == "string_pattern_mismatch":
        return (
            f"{field} só pode ter letras minúsculas sem acento, números, '-' e '_', "
            "começando por letra ou número"
        )
    if kind == "string_type":
        return f"{field} precisa ser um texto"
    if kind in {"int_type", "int_parsing", "int_from_float"}:
        return f"{field} precisa ser um número inteiro"
    if kind == "list_type":
        return f"{field} precisa ser uma lista"
    if kind in {"dict_type", "model_type", "model_attributes_type"}:
        return f"{field} precisa ser um bloco de campos"
    if kind == "greater_than_equal":
        return f"{field} precisa ser pelo menos {ctx.get('ge')}"
    if kind == "literal_error":
        return f"{field} tem um valor que não é aceito"
    if kind in {"union_tag_invalid", "union_tag_not_found"}:
        return f"{field}: tipo de condição desconhecido"
    return f"{field} não está certo ({item['msg']})"
