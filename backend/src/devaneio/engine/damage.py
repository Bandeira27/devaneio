"""Dano: por arma (fórmula rolada com os atributos do atacante) ou por quantia fixa.

hp tem piso em 0. Personagem com hp 0 está "fora de combate"; morte é decisão narrativa.
NPC com hp 0 fica ``alive=False``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from devaneio.rng import Rng
from devaneio.rules import DiceRoll, ExpressionError, RuleSystem, evaluate, parse
from devaneio.schema import Campaign, Character, Event, GameState, NpcState

from .errors import EngineError
from .lookup import combatant, npc_locations

# O fim da linha de um dano que derruba: a apresentação o tira quando mostra o selo de desfecho.
INCAPACITATED_SUFFIX = ", fora de combate"

TargetKind = Literal["character", "npc"]


@dataclass(frozen=True)
class DamageResult:
    """O novo estado depois de um dano, com o alvo, a quantia e o hp restante."""

    state: GameState
    target_kind: TargetKind
    target_id: str
    amount: int
    hp_before: int
    hp_after: int
    incapacitated: bool
    rolls: tuple[DiceRoll, ...]
    text: str


def deal_damage(
    state: GameState,
    campaign: Campaign,
    rules: RuleSystem,
    *,
    attacker_kind: TargetKind,
    attacker_id: str,
    weapon_id: str,
    target_kind: TargetKind,
    target_id: str,
) -> DamageResult:
    """Rola a fórmula da arma com os atributos do atacante e aplica ao alvo.

    Resultado negativo da fórmula vira 0. Não decide acerto: isso é um ``resolve_check``
    anterior, a cargo de quem orquestra.
    """
    attacker_name, attacker_attrs, _ = combatant(state, campaign, attacker_kind, attacker_id)
    weapon = next((w for w in rules.weapons if w.id == weapon_id), None)
    if weapon is None:
        raise EngineError(f"arma '{weapon_id}' não existe no sistema de regras")

    rng = Rng(state.rng_seed, state.rng_draws)
    try:
        rolled = evaluate(parse(weapon.damage), attacker_attrs, rng)
    except ExpressionError as exc:
        raise EngineError(f"arma '{weapon_id}': {exc}") from exc
    amount = max(0, rolled.total)

    dice_text = " ".join(f"{r.dice} {list(r.values)} " for r in rolled.rolls)
    target_name = combatant(state, campaign, target_kind, target_id)[0]
    text = (
        f"{attacker_name} ataca {target_name} com {weapon.name} ({weapon.damage}): "
        f"{dice_text}→ {amount} de dano"
    )
    return _hit(
        state,
        target_kind,
        target_id,
        amount,
        rolls=rolled.rolls,
        rng_draws=rng.draws,
        text=text,
        data={
            "attacker_kind": attacker_kind,
            "attacker_id": attacker_id,
            "weapon_id": weapon_id,
            "rolls": [{"dice": r.dice, "values": list(r.values)} for r in rolled.rolls],
        },
    )


def apply_damage(
    state: GameState,
    campaign: Campaign,
    *,
    target_kind: TargetKind,
    target_id: str,
    amount: int,
    source: str,
) -> DamageResult:
    """Dano de quantia fixa (armadilha, queda, veneno). ``source`` é texto livre para o log."""
    if amount < 0:
        raise EngineError("dano não pode ser negativo (cura é outra ação)")
    target_name = combatant(state, campaign, target_kind, target_id)[0]
    text = f"{target_name} sofre {amount} de dano ({source})"
    return _hit(
        state,
        target_kind,
        target_id,
        amount,
        rolls=(),
        rng_draws=state.rng_draws,
        text=text,
        data={"source": source},
    )


def _hit(
    state: GameState,
    target_kind: TargetKind,
    target_id: str,
    amount: int,
    *,
    rolls: tuple[DiceRoll, ...],
    rng_draws: int,
    text: str,
    data: dict[str, Any],
) -> DamageResult:
    new_state = state.model_copy(deep=True)
    target: Character | NpcState
    if target_kind == "character":
        target = new_state.characters[target_id]
        if target.hp <= 0:
            raise EngineError(f"personagem '{target_id}' já está fora de combate")
    else:
        target = new_state.npcs[target_id]
        if not target.alive or target.hp <= 0:
            raise EngineError(f"npc '{target_id}' já está fora de combate")

    hp_before = target.hp
    hp_after = max(0, hp_before - amount)
    target.hp = hp_after
    incapacitated = hp_after == 0
    if incapacitated and isinstance(target, NpcState):
        target.alive = False

    text = f"{text}, hp {hp_before} → {hp_after}" + (INCAPACITATED_SUFFIX if incapacitated else "")
    new_state.rng_draws = rng_draws
    new_state.events.append(
        Event(
            turn=state.turn,
            kind="damage",
            text=text,
            data={
                "target_kind": target_kind,
                "target_id": target_id,
                "amount": amount,
                "hp_before": hp_before,
                "hp_after": hp_after,
                "incapacitated": incapacitated,
                "npc_locations": npc_locations(
                    state,
                    (target_kind, target_id),
                    (str(data.get("attacker_kind")), str(data.get("attacker_id"))),
                ),
                **data,
            },
        )
    )
    return DamageResult(
        state=new_state,
        target_kind=target_kind,
        target_id=target_id,
        amount=amount,
        hp_before=hp_before,
        hp_after=hp_after,
        incapacitated=incapacitated,
        rolls=rolls,
        text=text,
    )
