"""Diretor de narrativa: determinístico, sem LLM.

Observa o estado, avalia as condições declaradas na campanha, faz NPCs hostis reagirem e
mede a tensão. Nunca inventa texto: só dispara ações do motor já existentes e registra um
evento ``director`` com o que fez. A tensão é derivada (não vive no estado) e, por enquanto,
apenas observada; usá-la para ritmo é trabalho futuro.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from devaneio.rng import Rng
from devaneio.rules import RuleSystem
from devaneio.schema import (
    BeatStatus,
    Campaign,
    Event,
    GameState,
)

from .beats import activate_beat, complete_beat
from .checks import npc_check
from .conditions import HIT, holds
from .damage import deal_damage
from .errors import EngineError
from .reveal import reveal_facts
from .turns import end_turn

TENSION_WEIGHTS = {"hp_lost": 0.4, "hostiles": 0.3, "down": 0.2, "failed": 0.1}


@dataclass(frozen=True)
class DirectorResult:
    state: GameState
    tension: float
    actions: tuple[str, ...]
    text: str


def advance_beats(state: GameState, campaign: Campaign) -> tuple[GameState, tuple[str, ...]]:
    """Conclui marcos ativos cujo ``complete_when`` (não vazio) vale e ativa pendentes com
    requisitos concluídos e ``activate_when`` valendo. Repete até estabilizar; termina
    porque cada mudança só avança um status."""
    texts: list[str] = []
    changed = True
    while changed:
        changed = False
        for beat in campaign.beats:
            status = state.beats.get(beat.id)
            if (
                status is BeatStatus.ACTIVE
                and beat.complete_when
                and all(holds(c, state) for c in beat.complete_when)
            ):
                result = complete_beat(state, campaign, beat_id=beat.id)
            elif (
                status is BeatStatus.PENDING
                and all(state.beats.get(r) is BeatStatus.DONE for r in beat.requires)
                and all(holds(c, state) for c in beat.activate_when)
            ):
                result = activate_beat(state, campaign, beat_id=beat.id)
            else:
                continue
            state, changed = result.state, True
            texts.append(result.text)
    return state, tuple(texts)


def hostile_reactions(
    state: GameState, campaign: Campaign, rules: RuleSystem
) -> tuple[GameState, tuple[str, ...]]:
    """Cada NPC vivo no local do grupo com disposição abaixo de ``hostile_below`` ataca um
    personagem de pé: um sorteio escolhe o alvo (sempre um, mesmo com um só alvo, para a
    sequência ser previsível), depois teste da habilidade da arma e dano em acerto."""
    texts: list[str] = []
    for npc in campaign.npcs:
        npc_state = state.npcs.get(npc.id)
        if (
            npc_state is None
            or not npc_state.alive
            or npc_state.hp <= 0
            or npc_state.location_id != state.current_location_id
            or npc_state.disposition >= rules.dispositions.hostile_below
        ):
            continue
        standing = [c.id for c in state.characters.values() if c.hp > 0]
        if not standing:
            texts.append(f"{npc.name} não encontra ninguém de pé para atacar.")
            continue
        weapon_id = npc.weapon_id or rules.combat.default_weapon
        weapon = next((w for w in rules.weapons if w.id == weapon_id), None)
        if weapon is None:
            raise EngineError(f"npc '{npc.id}': arma '{weapon_id}' não existe no sistema")

        rng = Rng(state.rng_seed, state.rng_draws)
        target_id = standing[rng.roll(len(standing)) - 1]
        state = state.model_copy(update={"rng_draws": rng.draws})

        check = npc_check(
            state,
            campaign,
            rules,
            npc_id=npc.id,
            skill_id=weapon.skill,
            difficulty_id=rules.combat.attack_difficulty,
        )
        state = check.state
        texts.append(check.text)
        if check.outcome in HIT:
            damage = deal_damage(
                state,
                campaign,
                rules,
                attacker_kind="npc",
                attacker_id=npc.id,
                weapon_id=weapon.id,
                target_kind="character",
                target_id=target_id,
            )
            state = damage.state
            texts.append(damage.text)
        else:
            texts.append("O ataque não acerta.")
    return state, tuple(texts)


def tension(state: GameState, rules: RuleSystem) -> float:
    """0 a 1: hp perdido pelo grupo, hostis presentes, personagens caídos, marcos falhos."""
    chars = list(state.characters.values())
    total_max = sum(c.max_hp for c in chars)
    hp_lost = 1 - sum(c.hp for c in chars) / total_max if total_max else 0.0
    down = sum(1 for c in chars if c.hp == 0) / len(chars) if chars else 0.0
    hostiles = sum(
        1
        for n in state.npcs.values()
        if n.alive
        and n.hp > 0
        and n.location_id == state.current_location_id
        and n.disposition < rules.dispositions.hostile_below
    )
    failed = (
        sum(1 for s in state.beats.values() if s is BeatStatus.FAILED) / len(state.beats)
        if state.beats
        else 0.0
    )
    w = TENSION_WEIGHTS
    value = (
        w["hp_lost"] * hp_lost
        + w["hostiles"] * min(1.0, hostiles / 2)
        + w["down"] * down
        + w["failed"] * failed
    )
    return round(min(1.0, value), 2)


def direct(state: GameState, campaign: Campaign, rules: RuleSystem) -> DirectorResult:
    """Uma passada do diretor: marcos, reações hostis, marcos de novo (quedas de NPC
    podem concluir algo), revelação de fatos, tensão, evento ``director``. Não muda o turno."""
    actions: list[str] = []
    state, texts = advance_beats(state, campaign)
    actions += texts
    state, texts = hostile_reactions(state, campaign, rules)
    actions += texts
    state, texts = advance_beats(state, campaign)
    actions += texts
    state, texts = reveal_facts(state, campaign)
    actions += texts

    level = tension(state, rules)
    summary = f"Diretor: tensão {level:.2f}; " + (
        f"{len(actions)} ação(ões)." if actions else "nada a fazer."
    )
    state = state.model_copy(deep=True)
    state.events.append(
        Event(
            turn=state.turn,
            kind="director",
            text=summary,
            data={"tension": level, "actions": actions},
        )
    )
    return DirectorResult(state, level, tuple(actions), "\n".join([*actions, summary]))


def pass_turn(state: GameState, campaign: Campaign, rules: RuleSystem) -> DirectorResult:
    """Fim de turno completo: diretor age no turno atual, depois ``end_turn``."""
    result = direct(state, campaign, rules)
    after = end_turn(result.state)
    text = f"{result.text}\nFim do turno {result.state.turn}. Começa o turno {after.turn}."
    return replace(result, state=after, text=text)
