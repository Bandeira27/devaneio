"""Validador de autoria: o que passa na validação mas quase certamente é engano do autor.

A validação (carga da campanha, do sistema e do pacote) recusa o que está quebrado. Aqui ficam os
achados em português que cruzam campanha, sistema e pacote: ``erro`` impede a campanha de funcionar
como o autor espera; ``aviso`` é um risco que ele pode aceitar de olhos abertos.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from devaneio.narration import NarrationPack, lint_pack
from devaneio.rules import RuleSystem
from devaneio.schema import AtLocation, Campaign, CheckPassed, Condition, NpcDown


@dataclass(frozen=True)
class Finding:
    level: Literal["erro", "aviso"]
    text: str

    def __str__(self) -> str:
        return f"{self.level}: {self.text}"


def check_content(campaign: Campaign, rules: RuleSystem, pack: NarrationPack) -> list[Finding]:
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
