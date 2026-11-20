import json

import pytest
from pydantic import ValidationError

from devaneio.engine import (
    activate_beat,
    add_character,
    advance_beats,
    apply_damage,
    complete_beat,
    deal_damage,
    fail_beat,
    heal,
    initial_state,
    move,
    pass_turn,
    resolve_check,
    rest,
    reveal_fact,
)
from devaneio.narration import (
    EVENT_VARIABLES,
    EVENT_VARIANTS,
    NarrationIntegrityError,
    NarrationPack,
    Narrator,
    PackExtendsError,
    builtin_pack_dict,
    builtin_pack_json,
    load_builtin_pack,
    load_pack,
    load_pack_extending,
    merge_pack,
    validate_pack,
)
from devaneio.schema import Event, FactDef


@pytest.fixture
def pack():
    return load_builtin_pack("pt-br")


@pytest.fixture
def narrator(campaign, rules, pack):
    return Narrator(campaign, rules, pack)


@pytest.fixture
def played(campaign, rules):
    """Uma partida curta com um evento de cada tipo."""
    s, _ = advance_beats(initial_state(campaign, rules, 8), campaign)
    s = add_character(s, rules, character_id="aria", name="Aria", attributes={"FOR": 3}).state
    s, _ = advance_beats(move(s, campaign, to_location_id="floresta").state, campaign)
    # chegada exige vila + persuadir: aqui o marco é concluído à mão, para gerar o beat_done
    s = complete_beat(s, campaign, beat_id="chegada").state
    s, _ = advance_beats(s, campaign)
    s, _ = advance_beats(move(s, campaign, to_location_id="ruinas").state, campaign)
    s = resolve_check(
        s, rules, character_id="aria", skill_id="investigar", difficulty_id="normal"
    ).state
    s = deal_damage(
        s,
        campaign,
        rules,
        attacker_kind="character",
        attacker_id="aria",
        weapon_id="espada",
        target_kind="npc",
        target_id="sacerdote",
    ).state
    s = apply_damage(
        s,
        campaign,
        target_kind="character",
        target_id="aria",
        amount=2,
        source="armadilha do altar",
    ).state
    s = pass_turn(s, campaign, rules).state  # diretor + turn_end (+ marcos)
    return s


# --- pacote -----------------------------------------------------------------------


def test_builtin_pack_is_coherent(pack):
    assert pack.id == "pt-br"
    assert validate_pack(pack) == []
    for kind in EVENT_VARIABLES:
        assert any(k == kind or k.startswith(f"{kind}.") for k in pack.rules), kind


def test_pack_rejects_undefined_references():
    data = json.loads(builtin_pack_json("pt-br"))
    data["rules"]["move"] = ["#origem# → #destinno#"]
    data["rules"]["eco_bom"] = ["#alvo#"]  # alcançado por check.*, que não oferece 'alvo'
    with pytest.raises(NarrationIntegrityError) as info:
        load_pack(data)
    assert info.value.errors == [
        "referência indefinida em check.success: #alvo#",
        "referência indefinida em move: #destinno#",
    ]


def test_pack_structure_errors():
    with pytest.raises(ValidationError):
        NarrationPack.model_validate({"id": "x", "language": "pt", "rules": {"a": []}})
    with pytest.raises(ValidationError):
        NarrationPack.model_validate({"id": "x", "language": "pt", "rules": {}})
    with pytest.raises(ValueError, match="não encontrado"):
        load_builtin_pack("klingon")


# --- narrador ---------------------------------------------------------------------


def test_every_event_kind_gets_prose(narrator, played):
    kinds = {e.kind for e in played.events}
    assert kinds >= {
        "character_joined",
        "move",
        "beat_done",
        "beat_activated",
        "check",
        "damage",
        "director",
        "turn_end",
    }
    for i, event in enumerate(played.events):
        text = narrator.narrate(event, i, played)
        assert text, event.kind
        assert text != event.text, (event.kind, text)
        assert "#" not in text
        assert "  " not in text


def test_narration_is_deterministic_and_does_not_touch_the_state(narrator, played):
    before = played.model_copy(deep=True)
    once = narrator.narrate_all(played)
    twice = narrator.narrate_all(played)
    assert once == twice
    assert played == before


def test_narration_varies_with_seed_and_index(narrator, played):
    event = next(e for e in played.events if e.kind == "move")
    texts = {narrator.narrate(event, i, played) for i in range(12)}
    assert len(texts) > 1
    other = played.model_copy(update={"rng_seed": played.rng_seed + 1})
    assert {narrator.narrate(event, i, other) for i in range(12)} != set()


def test_names_come_from_campaign_state_and_rules(narrator, played):
    by_kind = {}
    for i, e in enumerate(played.events):
        by_kind.setdefault(e.kind, (i, e))
    i, joined = by_kind["character_joined"]
    assert "Aria" in narrator.narrate(joined, i, played)
    i, mv = by_kind["move"]
    assert "Vila de Pedra Alta" in narrator.narrate(mv, i, played)
    assert "Floresta Cinzenta" in narrator.narrate(mv, i, played)
    i, chk = by_kind["check"]
    assert "Investigar" in narrator.narrate(chk, i, played)
    i, dmg = by_kind["damage"]
    text = narrator.narrate(dmg, i, played)
    assert "Irmão Vael" in text
    assert "Espada" in text
    i, beat = by_kind["beat_done"]
    assert "Chegada à vila" in narrator.narrate(beat, i, played)


def test_rule_keys_follow_variants(narrator, campaign, rules, played):
    keys = [narrator.rule_key(e, played) for e in played.events]
    assert "damage.golpe" in keys
    assert "damage.fonte" in keys
    check = next(e for e in played.events if e.kind == "check")
    assert narrator.rule_key(check, played) == f"check.{check.data['outcome']}"
    director = next(e for e in played.events if e.kind == "director")
    assert narrator.rule_key(director, played) in (
        "director.calmo",
        "director.tenso",
        "director.critico",
    )
    s = apply_damage(
        played, campaign, target_kind="character", target_id="aria", amount=99, source="queda"
    ).state
    assert narrator.rule_key(s.events[-1], s) == "damage.fonte_queda"
    assert "Aria" in narrator.narrate(s.events[-1], len(s.events) - 1, s)


def test_director_variant_by_tension(narrator, played):
    low = Event(turn=0, kind="director", text="x", data={"tension": 0.1, "actions": []})
    mid = Event(turn=0, kind="director", text="x", data={"tension": 0.4, "actions": []})
    high = Event(turn=0, kind="director", text="x", data={"tension": 0.9, "actions": []})
    assert [narrator.rule_key(e, played) for e in (low, mid, high)] == [
        "director.calmo",
        "director.tenso",
        "director.critico",
    ]
    assert "Ruínas do Templo" in narrator.narrate(high, 0, played)


def test_unknown_event_kind_falls_back_to_mechanical_text(narrator, played):
    event = Event(turn=0, kind="eclipse", text="O céu escurece.", data={})
    assert narrator.narrate(event, 0, played) == "O céu escurece."


def test_failed_beat_is_narrated(narrator, campaign, rules):
    s = initial_state(campaign, rules, 1)
    s = fail_beat(
        activate_beat(s, campaign, beat_id="chegada").state, campaign, beat_id="chegada"
    ).state
    assert "Chegada à vila" in narrator.narrate(s.events[-1], len(s.events) - 1, s)


def test_heal_and_rest_are_narrated(narrator, campaign, rules, played):
    s = apply_damage(
        played, campaign, target_kind="character", target_id="aria", amount=3, source="x"
    ).state
    healed = heal(s, campaign, target_kind="character", target_id="aria", amount=2, source="poção")
    i = len(healed.state.events) - 1
    prose = narrator.narrate(healed.state.events[i], i, healed.state)
    assert "Aria" in prose
    assert "poção" in prose
    assert prose != healed.text
    assert "#" not in prose

    cleared = apply_damage(
        healed.state, campaign, target_kind="npc", target_id="sacerdote", amount=99, source="x"
    ).state
    rested = rest(cleared, campaign, rules)
    j = len(rested.state.events) - 1
    prose = narrator.narrate(rested.state.events[j], j, rested.state)
    assert "Aria (+" in prose
    assert prose != rested.text
    assert "#" not in prose


def test_a_reveal_event_gets_prose_with_the_fact_text(campaign, rules, pack):
    with_fact = campaign.model_copy(update={"facts": [FactDef(id="culto", text="O culto é real.")]})
    state = reveal_fact(initial_state(with_fact, rules, 8), with_fact, fact_id="culto").state
    text = Narrator(with_fact, rules, pack).narrate(state.events[-1], len(state.events) - 1, state)
    assert "O culto é real." in text
    assert "#" not in text


# --- extends ----------------------------------------------------------------------------


def pack_extension(**fields):
    return {"id": "meu", "extends": "pt-br", **fields}


def test_a_pack_extension_replaces_keys_and_inherits_the_rest():
    parent = builtin_pack_dict("pt-br")
    child = load_pack_extending(
        pack_extension(rules={"move": ["Vocês seguem para #destino#."]}), builtin_pack_dict
    )
    assert child.id == "meu"
    assert child.language == parent["language"]
    assert child.rules["move"] == ["Vocês seguem para #destino#."]
    assert child.rules["check.success"] == parent["rules"]["check.success"]
    assert set(child.rules) == set(parent["rules"])


def test_a_pack_extension_can_add_new_keys():
    child = load_pack_extending(
        pack_extension(language="pt-PT", rules={"check.extra": ["#ator# tenta."]}),
        builtin_pack_dict,
    )
    assert child.language == "pt-PT"
    assert child.rules["check.extra"] == ["#ator# tenta."]


def test_merge_pack_does_not_mutate_its_inputs():
    parent = builtin_pack_dict("pt-br")
    before = json.loads(json.dumps(parent))
    merge_pack(parent, {"rules": {"move": ["x"]}})
    assert parent == before


def test_a_pack_extension_is_validated_like_a_full_pack():
    with pytest.raises(NarrationIntegrityError, match="destinno"):
        load_pack_extending(pack_extension(rules={"move": ["#destinno#"]}), builtin_pack_dict)


def test_pack_extends_errors_are_clear():
    parent = builtin_pack_dict("pt-br")
    with pytest.raises(PackExtendsError, match="estender a si mesmo"):
        load_pack_extending({"id": "x", "extends": "x"}, builtin_pack_dict)
    with pytest.raises(PackExtendsError, match="só um nível"):
        load_pack_extending(pack_extension(), lambda _id: {**parent, "extends": "outro"})
    with pytest.raises(PackExtendsError, match="repete o id"):
        load_pack_extending({"id": "pt-br", "extends": "meu"}, lambda _id: parent)
    with pytest.raises(ValueError, match="não encontrado"):
        load_pack_extending(pack_extension(extends="nada"), builtin_pack_dict)
    with pytest.raises(ValidationError, match="regra_x"):
        load_pack_extending(pack_extension(regra_x=[]), builtin_pack_dict)


def test_a_file_without_extends_is_a_plain_pack():
    text = builtin_pack_json("pt-br")
    assert load_pack_extending(text, builtin_pack_dict).id == "pt-br"


def test_the_narrator_only_uses_variants_the_table_knows(narrator, played):
    for event in played.events:
        variant, _ = narrator._prepare(event, played)
        assert variant == "" or variant in EVENT_VARIANTS.get(event.kind, ()), event.kind


def test_a_pack_extension_without_language_or_rules_inherits_everything():
    parent = builtin_pack_dict("pt-br")
    child = load_pack_extending({"id": "meu", "extends": "pt-br"}, builtin_pack_dict)
    assert child.language == parent["language"]
    assert child.rules == parent["rules"]


def test_a_pack_extension_cannot_empty_an_inherited_rule():
    with pytest.raises(ValidationError):
        load_pack_extending(pack_extension(rules={"move": []}), builtin_pack_dict)


def test_a_null_language_in_a_pack_extension_is_rejected_not_inherited():
    child = pack_extension(language=None)
    with pytest.raises(ValueError, match="language"):
        load_pack_extending(child, builtin_pack_dict)


def test_merge_pack_drops_extends_and_creates_missing_rules():
    merged = merge_pack({"id": "p"}, {"extends": "p", "id": "f", "rules": {"a": ["x"]}})
    assert merged == {"id": "f", "rules": {"a": ["x"]}}
