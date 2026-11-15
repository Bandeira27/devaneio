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
