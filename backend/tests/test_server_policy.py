"""Política da mesa: os papéis particionam os comandos do jogo e o fim de turno automático."""

from devaneio.game import COMMANDS, READ_ONLY, TableMeta
from devaneio.schema import GameState
from devaneio.server import policy


def test_roles_partition_exactly_the_game_commands():
    groups = [policy.PLAYER_READ, policy.JOIN, policy.ACTIONS, policy.HOST_ONLY]
    assert set().union(*groups) == set(COMMANDS)
    assert sum(len(g) for g in groups) == len(COMMANDS)  # nenhum comando em dois papéis


def test_every_command_gets_a_kind_and_unknown_ones_get_none():
    assert {policy.classify(name) for name in COMMANDS} == {"read", "join", "action", "host"}
    assert policy.classify("dançar") is None
    assert policy.classify("") is None


def test_marcos_is_the_hosts_because_it_lists_pending_beats():
    assert "marcos" in READ_ONLY
    assert policy.classify("marcos") == "host"
    assert policy.classify("log") == "host"  # o jogador lê o log filtrado por GET .../events
    assert policy.classify("olhar") == "read"
    assert policy.classify("ficha") == "read"


def test_fatos_and_revelar_are_the_hosts_because_they_expose_hidden_facts():
    assert "fatos" in READ_ONLY
    assert policy.classify("fatos") == "host"
    assert policy.classify("revelar") == "host"


def _state(**hp: int) -> GameState:
    characters = {
        cid: {"id": cid, "name": cid.title(), "hp": value, "max_hp": 10}
        for cid, value in hp.items()
    }
    return GameState.model_validate(
        {
            "campaign_id": "c",
            "rng_seed": 1,
            "current_location_id": "l",
            "turn": 3,
            "characters": characters,
        }
    )


def _table(acted: dict[str, int], **owners: list[str]) -> TableMeta:
    players = {
        pid: {"name": pid, "role": "player", "token_hash": "h", "character_ids": ids}
        for pid, ids in owners.items()
    }
    return TableMeta.model_validate({"invite_hash": "i", "players": players, "acted": acted})


def test_turn_ends_only_when_every_eligible_character_acted_this_turn():
    state = _state(ana=10, bia=10)
    table = _table({"ana": 3}, p1=["ana"], p2=["bia"])
    assert policy.everyone_acted(table, state) is False
    table = _table({"ana": 3, "bia": 3}, p1=["ana"], p2=["bia"])
    assert policy.everyone_acted(table, state) is True


def test_an_action_from_a_previous_turn_does_not_count():
    state = _state(ana=10, bia=10)
    table = _table({"ana": 3, "bia": 2}, p1=["ana"], p2=["bia"])
    assert policy.everyone_acted(table, state) is False


def test_a_fallen_character_does_not_hold_the_turn():
    state = _state(ana=10, bia=0)
    table = _table({"ana": 3}, p1=["ana"], p2=["bia"])
    assert policy.eligible(table, state) == ["ana"]
    assert policy.everyone_acted(table, state) is True


def test_nobody_eligible_never_ends_the_turn():
    state = _state(ana=0)
    assert policy.everyone_acted(_table({}, p1=["ana"]), state) is False
    assert policy.everyone_acted(_table({}, p1=[]), state) is False
    assert policy.everyone_acted(_table({}), state) is False


def test_characters_nobody_owns_are_not_waited_for():
    state = _state(ana=10, npc_aliado=10)
    table = _table({"ana": 3}, p1=["ana"])
    assert policy.eligible(table, state) == ["ana"]
    assert policy.everyone_acted(table, state) is True
