import pytest

from devaneio.engine import (
    add_character,
    advance_beats,
    apply_damage,
    complete_beat,
    direct,
    holds,
    initial_state,
    move,
    npc_check,
    pass_turn,
    tension,
)
from devaneio.rng import Rng
from devaneio.rules import CheckOutcome
from devaneio.schema import AtLocation, BeatDone, BeatStatus, NpcDown, TurnAtLeast

SEED = 21


@pytest.fixture
def state(campaign, rules):
    s = initial_state(campaign, rules, SEED)
    return add_character(s, rules, character_id="aria", name="Aria", attributes={"FOR": 3}).state


def at(state, campaign, *path):
    for loc in path:
        state = move(state, campaign, to_location_id=loc).state
    return state


# --- condições -----------------------------------------------------------------


def test_conditions(state, campaign):
    assert holds(AtLocation(kind="at_location", location_id="vila"), state)
    assert not holds(AtLocation(kind="at_location", location_id="ruinas"), state)
    assert not holds(NpcDown(kind="npc_down", npc_id="ferreiro"), state)
    down = apply_damage(state, campaign, target_kind="npc", target_id="ferreiro", amount=99, source="x").state
    assert holds(NpcDown(kind="npc_down", npc_id="ferreiro"), down)
    assert not holds(NpcDown(kind="npc_down", npc_id="fantasma"), state)
    assert not holds(BeatDone(kind="beat_done", beat_id="chegada"), state)
    assert holds(TurnAtLeast(kind="turn_at_least", turn=0), state)
    assert not holds(TurnAtLeast(kind="turn_at_least", turn=1), state)


# --- marcos --------------------------------------------------------------------


def test_advance_activates_root_beat_only(state, campaign):
    after, texts = advance_beats(state, campaign)
    assert texts == ("Marco ativado: Chegada à vila.",)
    assert after.beats == {"chegada": BeatStatus.ACTIVE, "pista": BeatStatus.PENDING, "confronto": BeatStatus.PENDING}
    again, texts2 = advance_beats(after, campaign)
    assert texts2 == () and again == after


def test_beats_follow_the_journey(state, campaign):
    s, _ = advance_beats(state, campaign)
    s, texts = advance_beats(at(s, campaign, "floresta"), campaign)
    assert texts == ("Marco concluído: Chegada à vila.",)  # pista exige ruínas
    s, texts = advance_beats(at(s, campaign, "ruinas"), campaign)
    assert texts == ("Marco ativado: A pista nas ruínas.",)
    assert s.beats["confronto"] is BeatStatus.PENDING  # exige pista concluída
    s, texts = advance_beats(s, campaign)
    assert texts == ()  # pista só conclui por ação explícita
    s = complete_beat(s, campaign, beat_id="pista").state
    s, texts = advance_beats(s, campaign)
    assert texts == ("Marco ativado: Confronto com o culto.",)
    s = apply_damage(s, campaign, target_kind="npc", target_id="sacerdote", amount=99, source="x").state
    s, texts = advance_beats(s, campaign)
    assert texts == ("Marco concluído: Confronto com o culto.",)
    assert set(s.beats.values()) == {BeatStatus.DONE}


# --- reações hostis ------------------------------------------------------------


def test_no_hostiles_in_the_village(state, campaign, rules):
    result = direct(state, campaign, rules)
    assert result.actions == ("Marco ativado: Chegada à vila.",)
    assert result.tension == 0.0
    assert result.text.endswith("Diretor: tensão 0.00; 1 ação(ões).")
    event = result.state.events[-1]
    assert event.kind == "director" and event.data == {"tension": 0.0, "actions": list(result.actions)}
    assert state.events[-1].kind == "character_joined"  # pureza


def test_hostile_priest_attacks_at_the_ruins(state, campaign, rules):
    s = at(state, campaign, "floresta", "ruinas")
    s, _ = advance_beats(s, campaign)
    rng = Rng(SEED, draws=s.rng_draws)
    rng.roll(1)  # sorteio do alvo (um só alvo, ainda assim um sorteio)
    predicted = npc_check(
        s.model_copy(update={"rng_draws": rng.draws}), campaign, rules,
        npc_id="sacerdote", skill_id="lutar", difficulty_id="normal",
    )
    result = direct(s, campaign, rules)
    kinds = [e.kind for e in result.state.events[len(s.events):]]
    assert result.actions[0] == predicted.text
    assert result.actions[0].startswith("Irmão Vael testa Lutar (2d6 + FOR) contra Normal 9:")
    if predicted.outcome in (CheckOutcome.SUCCESS, CheckOutcome.CRITICAL_SUCCESS):
        assert result.actions[1].startswith("Irmão Vael ataca Aria com Adaga (1d4 + FOR):")
        assert kinds == ["check", "damage", "director"]
        assert result.state.characters["aria"].hp < 12
    else:
        assert result.actions[1] == "O ataque não acerta."
        assert kinds == ["check", "director"]
        assert result.state.characters["aria"].hp == 12
    assert result.tension > 0  # hostil presente
    assert direct(s, campaign, rules) == result  # determinístico


def test_every_hostile_outcome_shows_up_over_seeds(campaign, rules):
    hits = misses = 0
    for seed in range(30):
        s = initial_state(campaign, rules, seed)
        s = add_character(s, rules, character_id="aria", name="Aria").state
        s = at(s, campaign, "floresta", "ruinas")
        result = direct(s, campaign, rules)
        if result.state.characters["aria"].hp < 10:
            hits += 1
        else:
            misses += 1
    assert hits and misses


def test_dead_or_friendly_npcs_do_not_attack(state, campaign, rules):
    s = at(state, campaign, "floresta", "ruinas")
    s = apply_damage(s, campaign, target_kind="npc", target_id="sacerdote", amount=99, source="x").state
    result = direct(s, campaign, rules)
    assert all("ataca" not in a for a in result.actions)
    assert result.tension == 0.0


def test_nobody_standing(state, campaign, rules):
    s = at(state, campaign, "floresta", "ruinas")
    s = apply_damage(s, campaign, target_kind="character", target_id="aria", amount=99, source="x").state
    result = direct(s, campaign, rules)
    assert "Irmão Vael não encontra ninguém de pé para atacar." in result.actions
    assert all(e.kind != "check" for e in result.state.events[len(s.events):])


def test_tension_formula(state, campaign, rules):
    s = at(state, campaign, "floresta", "ruinas")  # hostil presente: 0.3 * min(1, 1/2) = 0.15
    assert tension(s, rules) == 0.15
    half = apply_damage(s, campaign, target_kind="character", target_id="aria", amount=6, source="x").state
    assert tension(half, rules) == 0.35  # + 0.4 * 0.5
    down = apply_damage(s, campaign, target_kind="character", target_id="aria", amount=12, source="x").state
    assert tension(down, rules) == 0.75  # 0.4 * 1 + 0.15 + 0.2 * 1
    assert tension(state, rules) == 0.0


def test_pass_turn_runs_director_then_ends_turn(state, campaign, rules):
    result = pass_turn(state, campaign, rules)
    assert result.state.turn == 1
    assert [e.kind for e in result.state.events[-2:]] == ["director", "turn_end"]
    assert result.state.events[-2].turn == 0
    assert result.text.endswith("Fim do turno 0. Começa o turno 1.")
