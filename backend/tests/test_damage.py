import pytest

from devaneio.engine import EngineError, apply_damage, deal_damage, initial_state, resolve_check
from devaneio.rng import Rng
from devaneio.schema import Character, GameState, NpcState, validate_against_campaign

SEED = 99


@pytest.fixture
def state(campaign, rules) -> GameState:
    hero = Character(
        id="aria",
        name="Aria",
        attributes={"FOR": 2, "AGI": 3, "MEN": 1, "PRE": 2},
        hp=10,
        max_hp=10,
        inventory=["espada"],
    )
    return initial_state(campaign, rules, SEED, [hero])


def hit(state, campaign, **kw):
    kw.setdefault("target_kind", "character")
    kw.setdefault("target_id", "aria")
    kw.setdefault("source", "armadilha")
    return apply_damage(state, campaign, **kw)


def test_apply_damage_is_pure_and_logs(state, campaign):
    result = hit(state, campaign, amount=3)
    assert state.characters["aria"].hp == 10
    assert state.events == []
    assert (result.hp_before, result.hp_after, result.amount) == (10, 7, 3)
    assert result.state.characters["aria"].hp == 7
    assert result.incapacitated is False
    assert result.text == "Aria sofre 3 de dano (armadilha), hp 10 → 7"
    event = result.state.events[0]
    assert event.kind == "damage"
    assert event.turn == 0
    assert event.text == result.text
    assert event.data["source"] == "armadilha"
    assert event.data["hp_after"] == 7
    assert result.state.rng_draws == state.rng_draws


def test_damage_floors_at_zero_and_incapacitates(state, campaign):
    result = hit(state, campaign, amount=25)
    assert result.hp_after == 0
    assert result.incapacitated
    assert result.text.endswith("hp 10 → 0, fora de combate")
    assert "aria" in result.state.characters  # ninguém some do estado


def test_npc_at_zero_hp_is_no_longer_alive(state, campaign):
    result = hit(state, campaign, target_kind="npc", target_id="ferreiro", amount=10)
    npc = result.state.npcs["ferreiro"]
    assert (npc.hp, npc.alive) == (0, False)
    assert result.text.startswith("Bram sofre 10 de dano")
    survivor = hit(state, campaign, target_kind="npc", target_id="ferreiro", amount=9)
    assert survivor.state.npcs["ferreiro"].alive is True


def test_zero_damage_is_allowed(state, campaign):
    result = hit(state, campaign, amount=0)
    assert result.hp_after == 10
    assert not result.incapacitated


@pytest.mark.parametrize(
    ("kw", "fragment"),
    [
        ({"amount": -1}, "não pode ser negativo"),
        ({"amount": 1, "target_id": "ninguem"}, "personagem 'ninguem'"),
        ({"amount": 1, "target_kind": "npc", "target_id": "ninguem"}, "npc 'ninguem'"),
        ({"amount": 1, "target_kind": "monstro"}, "tipo de alvo desconhecido"),
    ],
)
def test_apply_damage_rejects_bad_input(state, campaign, kw, fragment):
    with pytest.raises(EngineError, match=fragment):
        hit(state, campaign, **kw)


def test_cannot_hit_someone_already_down(state, campaign):
    down = hit(state, campaign, amount=10).state
    with pytest.raises(EngineError, match="já está fora de combate"):
        hit(down, campaign, amount=1)
    dead = hit(state, campaign, target_kind="npc", target_id="ferreiro", amount=10).state
    with pytest.raises(EngineError, match="já está fora de combate"):
        hit(dead, campaign, target_kind="npc", target_id="ferreiro", amount=1)


def test_npc_in_state_but_not_in_campaign(state, campaign):
    state.npcs["fantasma"] = NpcState(hp=3, max_hp=3)
    with pytest.raises(EngineError, match="npc 'fantasma' não existe na campanha"):
        hit(state, campaign, target_kind="npc", target_id="fantasma", amount=1)


def test_deal_damage_rolls_weapon_with_attacker_attributes(state, campaign, rules):
    result = deal_damage(
        state,
        campaign,
        rules,
        attacker_kind="character",
        attacker_id="aria",
        weapon_id="espada",
        target_kind="npc",
        target_id="sacerdote",
    )
    die = Rng(SEED).roll(6)
    assert [v for r in result.rolls for v in r.values] == [die]
    assert result.amount == die + 2  # 1d6 + FOR da Aria
    assert (result.hp_before, result.hp_after) == (12, 12 - result.amount)
    assert result.state.rng_draws == 1
    assert result.text.startswith(
        f"Aria ataca Irmão Vael com Espada (1d6 + FOR): 1d6 [{die}] → {result.amount} de dano, hp 12 → "
    )
    data = result.state.events[0].data
    assert data["attacker_id"] == "aria"
    assert data["weapon_id"] == "espada"
    assert data["rolls"] == [{"dice": "1d6", "values": [die]}]


def test_npc_can_attack_with_its_own_attributes(state, campaign, rules):
    result = deal_damage(
        state,
        campaign,
        rules,
        attacker_kind="npc",
        attacker_id="sacerdote",
        weapon_id="punhos",
        target_kind="character",
        target_id="aria",
    )
    assert result.amount == 1 + 3  # punhos: 1 + FOR, sacerdote FOR 3
    assert result.rolls == ()
    assert result.state.rng_draws == 0
    assert result.text == "Irmão Vael ataca Aria com Punhos (1 + FOR): → 4 de dano, hp 10 → 6"


def test_deal_damage_unknown_weapon(state, campaign, rules):
    with pytest.raises(EngineError, match="arma 'canhao'"):
        deal_damage(
            state,
            campaign,
            rules,
            attacker_kind="character",
            attacker_id="aria",
            weapon_id="canhao",
            target_kind="npc",
            target_id="ferreiro",
        )


def test_check_then_damage_share_one_rng_sequence(state, campaign, rules):
    check = resolve_check(
        state, rules, character_id="aria", skill_id="lutar", difficulty_id="normal"
    )
    dmg = deal_damage(
        check.state,
        campaign,
        rules,
        attacker_kind="character",
        attacker_id="aria",
        weapon_id="espada",
        target_kind="npc",
        target_id="ferreiro",
    )
    rng = Rng(SEED)
    expected = [rng.roll(6), rng.roll(6), rng.roll(6)]
    assert list(check.rolls[0].values) + list(dmg.rolls[0].values) == expected
    assert dmg.state.rng_draws == 3
    assert [e.kind for e in dmg.state.events] == ["check", "damage"]


def test_state_after_damage_roundtrips(state, campaign, rules):
    result = deal_damage(
        state,
        campaign,
        rules,
        attacker_kind="character",
        attacker_id="aria",
        weapon_id="espada",
        target_kind="npc",
        target_id="ferreiro",
    )
    again = GameState.model_validate_json(result.state.model_dump_json())
    assert again == result.state
    assert validate_against_campaign(again, campaign) == []
