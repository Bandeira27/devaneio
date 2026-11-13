import pytest

from devaneio.engine import (
    EngineError,
    add_character,
    apply_damage,
    heal,
    initial_state,
    move,
    rest,
)
from devaneio.rng import Rng
from devaneio.schema import GameState, validate_against_campaign

SEED = 14


@pytest.fixture
def state(campaign, rules) -> GameState:
    s = initial_state(campaign, rules, SEED)
    s = add_character(s, rules, character_id="aria", name="Aria", attributes={"FOR": 3}).state
    return add_character(s, rules, character_id="zed", name="Zed").state  # FOR 2, hp 10


def hurt(state, campaign, who, amount, kind="character"):
    return apply_damage(state, campaign, target_kind=kind, target_id=who, amount=amount, source="x").state


def test_heal_is_pure_capped_and_logged(state, campaign):
    s = hurt(state, campaign, "aria", 8)  # 12 -> 4
    r = heal(s, campaign, target_kind="character", target_id="aria", amount=3, source="poção")
    assert s.characters["aria"].hp == 4
    assert (r.hp_before, r.hp_after, r.amount) == (4, 7, 3)
    assert r.text == "Aria recupera 3 de vida (poção), hp 4 → 7"
    event = r.state.events[-1]
    assert event.kind == "heal" and event.data["hp_after"] == 7 and event.data["source"] == "poção"
    big = heal(s, campaign, target_kind="character", target_id="aria", amount=99, source="milagre")
    assert big.hp_after == 12 and big.amount == 8


def test_heal_revives_a_downed_character(state, campaign):
    s = hurt(state, campaign, "zed", 99)
    assert s.characters["zed"].hp == 0
    r = heal(s, campaign, target_kind="character", target_id="zed", amount=4, source="poção")
    assert r.state.characters["zed"].hp == 4


def test_heal_npc_alive_but_not_dead(state, campaign):
    s = hurt(state, campaign, "ferreiro", 4, kind="npc")
    r = heal(s, campaign, target_kind="npc", target_id="ferreiro", amount=2, source="curandeira")
    assert r.state.npcs["ferreiro"].hp == 8 and r.text.startswith("Bram recupera 2")
    dead = hurt(state, campaign, "ferreiro", 99, kind="npc")
    with pytest.raises(EngineError, match="está morto"):
        heal(dead, campaign, target_kind="npc", target_id="ferreiro", amount=5, source="x")


@pytest.mark.parametrize(
    "kw, fragment",
    [
        ({"amount": 0}, "precisa ser positiva"),
        ({"amount": -2}, "precisa ser positiva"),
        ({"amount": 1}, "já está com o hp máximo"),
        ({"amount": 1, "target_id": "ninguem"}, "personagem 'ninguem'"),
    ],
)
def test_heal_rejects_bad_input(state, campaign, kw, fragment):
    kw = {"target_kind": "character", "target_id": "aria", "source": "x", **kw}
    with pytest.raises(EngineError, match=fragment):
        heal(state, campaign, **kw)


def test_rest_heals_each_hurt_character_with_the_system_formula(state, campaign, rules):
    s = hurt(hurt(state, campaign, "aria", 9), campaign, "zed", 6)  # aria 3/12, zed 4/10
    rng = Rng(SEED, draws=s.rng_draws)
    aria_gain = rng.roll(6) + 3
    zed_gain = rng.roll(6) + 2
    r = rest(s, campaign, rules)
    assert s.characters["aria"].hp == 3  # pureza
    assert r.healed == {
        "aria": (3, min(12, 3 + aria_gain)),
        "zed": (4, min(10, 4 + zed_gain)),
    }
    assert r.state.rng_draws == s.rng_draws + 2
    event = r.state.events[-1]
    assert event.kind == "rest" and set(event.data["healed"]) == {"aria", "zed"}
    assert r.text.startswith("O grupo descansa: Aria +") and "Zed +" in r.text
    assert validate_against_campaign(r.state, campaign) == []
    assert rest(s, campaign, rules) == r  # determinístico


def test_rest_skips_those_at_full_hp(state, campaign, rules):
    s = hurt(state, campaign, "zed", 5)
    r = rest(s, campaign, rules)
    assert set(r.healed) == {"zed"} and r.state.rng_draws == s.rng_draws + 1


def test_rest_revives_the_downed(state, campaign, rules):
    s = hurt(state, campaign, "aria", 99)
    r = rest(s, campaign, rules)
    assert r.state.characters["aria"].hp > 0


def test_rest_refused_cases(state, campaign, rules):
    with pytest.raises(EngineError, match="todos já estão com o hp máximo"):
        rest(state, campaign, rules)
    with pytest.raises(EngineError, match="não há personagens"):
        rest(initial_state(campaign, rules, 1), campaign, rules)
    at_ruins = move(move(hurt(state, campaign, "aria", 5), campaign, to_location_id="floresta").state, campaign, to_location_id="ruinas").state
    with pytest.raises(EngineError, match="Irmão Vael hostil por perto"):
        rest(at_ruins, campaign, rules)
    cleared = hurt(at_ruins, campaign, "sacerdote", 99, kind="npc")
    assert rest(cleared, campaign, rules).state.characters["aria"].hp > 7
