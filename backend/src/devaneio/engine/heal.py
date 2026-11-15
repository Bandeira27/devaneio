"""Cura (quantia fixa) e descanso (fórmula do sistema, só sem hostis por perto).

hp tem teto em max_hp. Curar quem está com hp 0 o põe de pé de novo (personagem "fora de
combate" não está morto). NPC com ``alive=False`` não é curado: morte de NPC é definitiva.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from devaneio.rng import Rng
from devaneio.rules import ExpressionError, RuleSystem, evaluate, parse
from devaneio.schema import Campaign, Character, Event, GameState, NpcState

from .damage import TargetKind
from .errors import EngineError
from .lookup import combatant, npc_locations


@dataclass(frozen=True)
class HealResult:
    state: GameState
    target_kind: TargetKind
    target_id: str
    amount: int  # efetivamente recuperado (já limitado por max_hp)
    hp_before: int
    hp_after: int
    text: str


@dataclass(frozen=True)
class RestResult:
    state: GameState
    healed: dict[str, tuple[int, int]]  # id -> (hp antes, hp depois)
    text: str


def heal(
    state: GameState,
    campaign: Campaign,
    *,
    target_kind: TargetKind,
    target_id: str,
    amount: int,
    source: str,
) -> HealResult:
    """Cura de quantia fixa (poção, magia). ``source`` é texto livre para o log."""
    if amount <= 0:
        raise EngineError("a cura precisa ser positiva (dano é outra ação)")
    name = combatant(state, campaign, target_kind, target_id)[0]
    new_state = state.model_copy(deep=True)
    before, after = _raise_hp(new_state, target_kind, target_id, amount)
    gained = after - before
    text = f"{name} recupera {gained} de vida ({source}), hp {before} → {after}"
    new_state.events.append(
        Event(
            turn=state.turn,
            kind="heal",
            text=text,
            data={
                "target_kind": target_kind,
                "target_id": target_id,
                "npc_locations": npc_locations(state, (target_kind, target_id)),
                "amount": gained,
                "hp_before": before,
                "hp_after": after,
                "source": source,
            },
        )
    )
    return HealResult(new_state, target_kind, target_id, gained, before, after, text)


def rest(state: GameState, campaign: Campaign, rules: RuleSystem) -> RestResult:
    """Todo personagem machucado rola ``rules.rest.heal`` com os próprios atributos e
    recupera hp (teto max_hp). Recusado sem personagens, com hostil vivo no local ou se
    ninguém precisa de descanso. Não avança o turno: quem orquestra compõe com o diretor."""
    if not state.characters:
        raise EngineError("não há personagens para descansar")
    hostile = _hostiles_present(state, campaign, rules)
    if hostile:
        raise EngineError(f"não dá para descansar: {', '.join(hostile)} hostil por perto")
    hurt = [c for c in state.characters.values() if c.hp < c.max_hp]
    if not hurt:
        raise EngineError("todos já estão com o hp máximo")

    rng = Rng(state.rng_seed, state.rng_draws)
    formula = parse(rules.rest.heal)
    new_state = state.model_copy(deep=True)
    healed: dict[str, tuple[int, int]] = {}
    details: dict[str, dict[str, Any]] = {}
    for char in hurt:
        try:
            rolled = evaluate(formula, char.attributes, rng)
        except ExpressionError as exc:
            raise EngineError(f"rest.heal de '{char.id}': {exc}") from exc
        before, after = _raise_hp(new_state, "character", char.id, max(0, rolled.total))
        healed[char.id] = (before, after)
        details[char.id] = {
            "amount": after - before,
            "hp_before": before,
            "hp_after": after,
            "rolls": [{"dice": r.dice, "values": list(r.values)} for r in rolled.rolls],
        }

    parts = [
        f"{state.characters[cid].name} +{after - before} (hp {before} → {after})"
        for cid, (before, after) in healed.items()
    ]
    text = "O grupo descansa: " + ", ".join(parts)
    new_state.rng_draws = rng.draws
    new_state.events.append(
        Event(turn=state.turn, kind="rest", text=text, data={"healed": details})
    )
    return RestResult(new_state, healed, text)


def _raise_hp(state: GameState, kind: TargetKind, who_id: str, amount: int) -> tuple[int, int]:
    """Aplica a cura no estado (mutando-o) e devolve (hp antes, hp depois)."""
    target: Character | NpcState
    if kind == "character":
        target = state.characters[who_id]
    else:
        target = state.npcs[who_id]
        if not target.alive:
            raise EngineError(f"npc '{who_id}' está morto e não pode ser curado")
    if target.hp >= target.max_hp:
        raise EngineError(f"'{who_id}' já está com o hp máximo")
    before = target.hp
    target.hp = min(target.max_hp, before + amount)
    return before, target.hp


def _hostiles_present(state: GameState, campaign: Campaign, rules: RuleSystem) -> list[str]:
    names = {n.id: n.name for n in campaign.npcs}
    return [
        names.get(npc_id, npc_id)
        for npc_id, npc in state.npcs.items()
        if npc.alive
        and npc.hp > 0
        and npc.location_id == state.current_location_id
        and npc.disposition < rules.dispositions.hostile_below
    ]
