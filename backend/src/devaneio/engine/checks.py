"""Teste de habilidade: rola a fórmula, compara com a dificuldade, registra o evento."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Protocol, TypeVar

from devaneio.rng import Rng
from devaneio.rules import (
    CheckOutcome,
    DiceRoll,
    ExpressionError,
    Outcomes,
    RuleSystem,
    evaluate,
    parse,
)
from devaneio.schema import Campaign, Event, GameState

from .errors import EngineError
from .lookup import combatant, npc_locations

OUTCOME_LABELS = {
    CheckOutcome.CRITICAL_FAILURE: "falha crítica",
    CheckOutcome.FAILURE: "falha",
    CheckOutcome.SUCCESS: "sucesso",
    CheckOutcome.CRITICAL_SUCCESS: "sucesso crítico",
}


def classify_outcome(margin: int, outcomes: Outcomes) -> CheckOutcome:
    """Margem = total - dificuldade. Negativa é falha; as caudas são os críticos."""
    if margin <= outcomes.critical_failure_margin:
        return CheckOutcome.CRITICAL_FAILURE
    if margin < 0:
        return CheckOutcome.FAILURE
    if margin >= outcomes.critical_success_margin:
        return CheckOutcome.CRITICAL_SUCCESS
    return CheckOutcome.SUCCESS


@dataclass(frozen=True)
class CheckResult:
    """O novo estado depois de um teste, com quem testou e o grau obtido."""

    state: GameState
    actor_kind: str  # "character" | "npc"
    actor_id: str
    skill_id: str
    difficulty_id: str
    modifier_id: str | None
    rolls: tuple[DiceRoll, ...]
    total: int
    difficulty: int
    margin: int
    outcome: CheckOutcome
    text: str


def resolve_check(
    state: GameState,
    rules: RuleSystem,
    *,
    character_id: str,
    skill_id: str,
    difficulty_id: str,
    modifier_id: str | None = None,
    attack: bool = False,
) -> CheckResult:
    """Teste de um personagem.

    Não altera ``state``: devolve um novo estado com ``rng_draws`` avançado e um ``Event`` de
    tipo ``check`` no log. O turno não muda aqui. ``attack`` marca o teste como o ataque de uma
    arma (``data["attack"]``), para a apresentação dizer acerto e erro em vez de sucesso e falha.
    """
    character = state.characters.get(character_id)
    if character is None:
        raise EngineError(f"personagem '{character_id}' não está no estado")
    return _resolve(
        state,
        rules,
        actor_kind="character",
        actor_id=character_id,
        actor_name=character.name,
        attributes=character.attributes,
        skill_id=skill_id,
        difficulty_id=difficulty_id,
        modifier_id=modifier_id,
        attack=attack,
    )


def npc_check(
    state: GameState,
    campaign: Campaign,
    rules: RuleSystem,
    *,
    npc_id: str,
    skill_id: str,
    difficulty_id: str,
    modifier_id: str | None = None,
) -> CheckResult:
    """Teste de um NPC, com os atributos do estado e o nome da campanha."""
    name, attributes, _ = combatant(state, campaign, "npc", npc_id)
    return _resolve(
        state,
        rules,
        actor_kind="npc",
        actor_id=npc_id,
        actor_name=name,
        attributes=attributes,
        skill_id=skill_id,
        difficulty_id=difficulty_id,
        modifier_id=modifier_id,
        attack=False,
    )


def _resolve(
    state: GameState,
    rules: RuleSystem,
    *,
    actor_kind: str,
    actor_id: str,
    actor_name: str,
    attributes: Mapping[str, int],
    skill_id: str,
    difficulty_id: str,
    modifier_id: str | None,
    attack: bool,
) -> CheckResult:
    skill = _find(rules.skills, skill_id, "habilidade")
    difficulty = _find(rules.difficulties, difficulty_id, "dificuldade")
    modifier = _find(rules.modifiers, modifier_id, "modificador") if modifier_id else None

    rng = Rng(state.rng_seed, state.rng_draws)
    try:
        rolled = evaluate(parse(skill.formula), attributes, rng)
    except ExpressionError as exc:
        raise EngineError(f"habilidade '{skill_id}': {exc}") from exc

    total = rolled.total + (modifier.value if modifier else 0)
    margin = total - difficulty.value
    outcome = classify_outcome(margin, rules.outcomes)

    dice_text = " ".join(f"{r.dice} {list(r.values)}" for r in rolled.rolls)
    formula_text = skill.formula + (f", {modifier.name}" if modifier else "")
    text = (
        f"{actor_name} testa {skill.name} ({formula_text}) contra "
        f"{difficulty.name} {difficulty.value}: {dice_text} → total {total}, "
        f"{OUTCOME_LABELS[outcome]}"
    )

    new_state = state.model_copy(deep=True)
    new_state.rng_draws = rng.draws
    new_state.events.append(
        Event(
            turn=state.turn,
            kind="check",
            text=text,
            data={
                "actor_kind": actor_kind,
                "actor_id": actor_id,
                "npc_locations": npc_locations(state, (actor_kind, actor_id)),
                "skill_id": skill_id,
                "difficulty_id": difficulty_id,
                "modifier_id": modifier_id,
                "rolls": [{"dice": r.dice, "values": list(r.values)} for r in rolled.rolls],
                "total": total,
                "difficulty": difficulty.value,
                "margin": margin,
                "outcome": outcome.value,
                "attack": attack,
            },
        )
    )
    return CheckResult(
        state=new_state,
        actor_kind=actor_kind,
        actor_id=actor_id,
        skill_id=skill_id,
        difficulty_id=difficulty_id,
        modifier_id=modifier_id,
        rolls=rolled.rolls,
        total=total,
        difficulty=difficulty.value,
        margin=margin,
        outcome=outcome,
        text=text,
    )


class _HasId(Protocol):
    @property
    def id(self) -> str: ...


T = TypeVar("T", bound=_HasId)


def _find(items: Iterable[T], item_id: str, label: str) -> T:
    for item in items:
        if item.id == item_id:
            return item
    raise EngineError(f"{label} '{item_id}' não existe no sistema de regras")
