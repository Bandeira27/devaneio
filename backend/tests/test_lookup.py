"""O critério de "quem está aqui" é um só, usado pelo olhar, pelas visões da mesa e pelo filtro."""

from conftest import CAMPAIGN_PATH
from devaneio.engine import npc_ids_at
from devaneio.game import execute, new_game


def test_npcs_are_found_by_location(tmp_path):
    session = new_game(CAMPAIGN_PATH, tmp_path / "p.json", seed=1)
    state = session.state
    assert npc_ids_at(state, "vila") == {"ferreiro"}
    assert npc_ids_at(state, "ruinas") == {"sacerdote"}
    assert npc_ids_at(state, "floresta") == frozenset()
    assert npc_ids_at(state, "nao-existe") == frozenset()


def test_the_look_command_lists_exactly_those_npcs(tmp_path):
    session = new_game(CAMPAIGN_PATH, tmp_path / "p.json", seed=1)
    _, text = execute(session, "olhar")
    assert "Bram (ferreiro)" in text
    assert "Irmão Vael" not in text


def test_events_record_where_the_npcs_involved_were(tmp_path):
    session = new_game(CAMPAIGN_PATH, tmp_path / "p.json", seed=1)
    state, _ = execute(session, 'entrar bia "Bia"')
    state, _ = execute(state, 'ferir sacerdote 2 "a"')
    state, _ = execute(state, 'curar sacerdote 1 "b"')
    state, _ = execute(state, 'ferir bia 1 "c"')
    state, _ = execute(state, "atacar punhos ferreiro")
    by_kind = {}
    for event in state.state.events:
        if event.kind in {"damage", "heal", "check"}:
            by_kind.setdefault(event.kind, []).append(event.data["npc_locations"])
    assert by_kind["damage"] == [{"sacerdote": "ruinas"}, {}, {"ferreiro": "vila"}]
    assert by_kind["heal"] == [{"sacerdote": "ruinas"}]
    assert by_kind["check"] == [{}]  # quem testou foi a Bia: nenhum NPC


def test_an_npc_attacker_is_recorded_too(tmp_path):
    session = new_game(CAMPAIGN_PATH, tmp_path / "p.json", seed=1)
    state, _ = execute(session, 'entrar bia "Bia" FOR=5')
    state, _ = execute(state, "ir floresta")
    state, _ = execute(state, "ir ruinas")
    state, _ = execute(state, "fim")  # o sacerdote hostil ataca
    npc_events = [
        e for e in state.state.events if e.data.get("npc_locations") == {"sacerdote": "ruinas"}
    ]
    assert {"check"} <= {e.kind for e in npc_events}
