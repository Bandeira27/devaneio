"""O que um jogador comum não vê do log: eventos sobre NPC que o grupo não via na hora."""

import threading
import time
from itertools import count

import pytest

from conftest import CAMPAIGN_PATH
from devaneio.game import CommandError, execute, new_game
from devaneio.server import ApiFailure, Catalog, Storage, TableService
from devaneio.server.models import (
    CampaignView,
    CommandRequest,
    CreateTableRequest,
    JoinRequest,
    PlayerStateView,
)
from devaneio.server.turns import PARTICIPANT_KEYS, events_view, hidden_events, hidden_for

TOKENS = count(1)


class Desk:
    def __init__(self, service):
        self.service = service
        created = service.create_table(
            CreateTableRequest(campaign_id="sombra-do-vale", host_name="Ana", seed=7)
        )
        self.id, self.host = created.table_id, created.host_token
        joined = service.join_table(self.id, JoinRequest(invite_code="convite", name="Bia"))
        self.bia = joined.token
        self.cmd(self.bia, 'entrar bia "Bia" FOR=5')

    def revision(self, token):
        return self.service.get_table(self.id, token).revision

    def cmd(self, token, line):
        request = CommandRequest(line=line, revision=self.revision(token))
        return self.service.run_command(self.id, token, request)

    def events(self, token, since=0, wait=0):
        return self.service.get_events(self.id, token, since, wait=wait)


@pytest.fixture
def desk(tmp_path):
    service = TableService(
        Catalog(CAMPAIGN_PATH.parent),
        Storage(tmp_path / "mesas", max_tables=4),
        token_source=lambda: f"token-{next(TOKENS)}",
        invite_source=lambda: "convite",
    )
    return Desk(service)


def kinds(view):
    return [e.kind for e in view.events]


def test_a_player_does_not_see_what_the_host_does_to_a_hidden_npc(desk):
    desk.cmd(desk.host, 'ferir sacerdote 2 "armadilha"')  # o sacerdote está nas ruínas
    desk.cmd(desk.bia, "testar lutar normal")  # um evento visível depois do escondido
    host_view, bia_view = desk.events(desk.host), desk.events(desk.bia)
    assert "Irmão Vael" in " ".join(e.text for e in host_view.events)
    assert "Irmão Vael" not in " ".join(e.text for e in bia_view.events)
    assert host_view.revision == bia_view.revision  # a revisão conta todos os eventos
    hidden = len(host_view.events) - len(bia_view.events)
    assert hidden == 1
    assert 2 not in [e.index for e in bia_view.events]  # o escondido é o de índice 2
    indexes = [e.index for e in bia_view.events]
    assert indexes != list(range(len(indexes)))  # o índice original fica: há um buraco


def test_the_result_of_a_command_is_filtered_for_who_receives_it(desk):
    result = desk.cmd(desk.host, 'ferir sacerdote 2 "armadilha"')
    assert kinds(result) == ["damage"]  # o anfitrião recebe o que fez
    bia_session_events = desk.events(desk.bia, since=result.revision - 1).events
    assert bia_session_events == []


def test_what_is_hidden_stays_hidden_after_the_group_arrives(desk):
    desk.cmd(desk.host, 'ferir sacerdote 2 "armadilha"')
    before = desk.events(desk.bia)
    desk.cmd(desk.bia, "ir floresta")
    desk.cmd(desk.bia, "ir ruinas")  # o grupo chega ao sacerdote
    after = desk.events(desk.bia)
    assert "Irmão Vael sofre" not in " ".join(
        e.text for e in after.events
    )  # a armadilha segue escondida
    assert [e.index for e in after.events][: len(before.events)] == [e.index for e in before.events]
    desk.cmd(desk.host, 'ferir sacerdote 1 "outra"')
    now_visible = desk.events(desk.bia, since=after.revision)
    assert "Irmão Vael sofre 1" in " ".join(e.text for e in now_visible.events)


def test_reading_with_since_never_loses_a_visible_event(desk):
    seen = desk.events(desk.bia).revision
    desk.cmd(desk.host, 'ferir sacerdote 2 "armadilha"')  # escondido
    assert desk.events(desk.bia, since=seen).events == []
    desk.cmd(desk.bia, "testar lutar normal")
    later = desk.events(desk.bia, since=seen)
    assert kinds(later)[0] == "check"


def test_a_hidden_write_wakes_the_poller_but_gives_it_no_event(desk):
    revision = desk.events(desk.bia).revision
    box = {}

    def poll():
        started = time.monotonic()
        box["view"] = desk.events(desk.bia, since=revision, wait=0.8)
        box["elapsed"] = time.monotonic() - started

    thread = threading.Thread(target=poll)
    thread.start()
    desk.cmd(desk.host, 'ferir sacerdote 2 "armadilha"')
    thread.join(timeout=10)
    assert box["view"].events == []
    assert box["view"].revision == revision + 1  # a revisão avançou, o evento não aparece
    assert box["elapsed"] >= 0.7  # esperou o prazo: o evento escondido não conta como novidade


def test_the_log_command_is_the_hosts(desk):
    with pytest.raises(ApiFailure) as info:
        desk.cmd(desk.bia, "log")
    assert (info.value.status, info.value.code) == (403, "forbidden")
    assert "Irmão Vael" in desk.cmd(desk.host, 'ferir sacerdote 2 "x"').text
    assert "Irmão Vael" in desk.cmd(desk.host, "log").text


# --- a função pura ------------------------------------------------------------------


@pytest.fixture
def session(tmp_path):
    base = new_game(CAMPAIGN_PATH, tmp_path / "p.json", seed=7)
    base, _ = execute(base, 'entrar bia "Bia"')
    return base


def test_hidden_events_follow_where_the_group_was_when_it_happened(session):
    state, _ = execute(session, 'ferir sacerdote 2 "a"')  # na vila: escondido
    state, _ = execute(state, 'ferir ferreiro 1 "b"')  # o ferreiro está na vila: visível
    state, _ = execute(state, "ir floresta")
    state, _ = execute(state, "ir ruinas")
    state, _ = execute(state, 'ferir sacerdote 1 "c"')  # agora o grupo está lá: visível
    hidden = hidden_events(state.state, state.campaign)
    damages = [i for i, e in enumerate(state.state.events) if e.kind == "damage"]
    assert len(damages) == 3
    assert hidden == {damages[0]}


def test_events_without_an_npc_are_never_hidden(session):
    state, _ = execute(session, "ir floresta")
    state, _ = execute(state, "bia: testar lutar normal")
    assert hidden_events(state.state, state.campaign) == frozenset()


# --- a invariante contra eventos reais do motor ------------------------------------

NPC_IDS = {"ferreiro", "sacerdote"}
ID_KEYS = {id_key for _, id_key in PARTICIPANT_KEYS}


def values(data):
    """Todos os valores (folhas) de um ``Event.data``, com a chave de cada um."""
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, dict | list):
                yield from values(value)
            else:
                yield key, value
    elif isinstance(data, list):
        for item in data:
            yield from values(item)
    else:
        yield "", data


@pytest.fixture
def busy(tmp_path):
    """Uma partida com os tipos de evento que citam NPC: dano, cura, teste e ataque do NPC,
    ataque do personagem, descanso, marcos e movimento."""
    base = new_game(CAMPAIGN_PATH, tmp_path / "p.json", seed=7)
    state, _ = execute(base, 'entrar bia "Bia" FOR=5')
    for line in (
        'ferir sacerdote 2 "a"',
        'curar sacerdote 1 "b"',
        'ferir ferreiro 1 "c"',
        "atacar punhos ferreiro",
        "bia: atacar punhos ferreiro",
        "ir floresta",
        "ir ruinas",
        "fim",
        "fim",
        'ferir bia 3 "d"',
        "descansar",
    ):
        try:
            state, _ = execute(state, line)
        except CommandError:
            continue  # o cenário só precisa gerar eventos; uma recusa do motor não importa
    return state


def test_every_npc_id_in_the_engine_events_sits_under_a_participant_key(busy):
    """Se o motor passar a citar NPC em outra chave de ``data``, o filtro do log vazaria nome e
    hp: este teste falha antes (o novo par entra em PARTICIPANT_KEYS)."""
    kinds_seen = set()
    for event in busy.state.events:
        kinds_seen.add(event.kind)
        for key, value in values(event.data):
            if value in NPC_IDS:
                assert key in ID_KEYS, f"{event.kind}: NPC '{value}' em data['{key}']"
    assert {"damage", "heal", "check", "move", "director"} <= kinds_seen


def test_an_event_that_names_a_hidden_npc_is_hidden(tmp_path):
    base = new_game(CAMPAIGN_PATH, tmp_path / "p.json", seed=7)
    state, _ = execute(base, 'entrar bia "Bia"')
    for line in ('ferir sacerdote 5 "a"', 'curar sacerdote 2 "b"', 'ferir sacerdote 99 "c"'):
        state, _ = execute(state, line)  # o grupo está na vila; o sacerdote, nas ruínas
    hidden = hidden_events(state.state, state.campaign)
    named = [i for i, e in enumerate(state.state.events) if "Irmão Vael" in e.text]
    assert len(named) == 3
    assert set(named) <= hidden


# --- o que continua visível, o papel e as visões ------------------------------------


def test_the_host_hides_nothing_and_events_view_needs_a_role(session):
    state, _ = execute(session, 'ferir sacerdote 2 "a"')  # escondido do grupo, que está na vila
    assert hidden_events(state.state, state.campaign) == {2}
    assert hidden_for("host", state) == frozenset()
    assert hidden_for("player", state) == {2}
    host_indexes = [e.index for e in events_view(state, 0, role="host")]
    player_indexes = [e.index for e in events_view(state, 0, role="player")]
    assert 2 in host_indexes
    assert 2 not in player_indexes
    with pytest.raises(TypeError, match="role"):
        events_view(state, 0)


def test_npc_heal_rest_and_director_events_with_a_visible_npc_reach_the_player(session):
    state, _ = execute(session, 'ferir ferreiro 2 "a"')
    state, _ = execute(state, 'curar ferreiro 1 "b"')
    state, _ = execute(state, 'ferir bia 3 "c"')
    state, _ = execute(state, "descansar")
    state, _ = execute(state, "ir floresta")
    state, _ = execute(state, "ir ruinas")
    state, _ = execute(state, "fim")  # o sacerdote hostil age: eventos de diretor
    seen = {e.kind for e in events_view(state, 0, role="player")}
    assert {"heal", "rest", "director"} <= seen
    assert hidden_events(state.state, state.campaign) == frozenset()


def test_player_views_list_the_npcs_of_the_current_location(session):
    state = session.state
    assert list(PlayerStateView.of(state, session.rules).npcs) == ["ferreiro"]
    assert [n.id for n in CampaignView.of(session.campaign, state).npcs] == ["ferreiro"]
    moved, _ = execute(session, "ir floresta")
    moved, _ = execute(moved, "ir ruinas")
    assert list(PlayerStateView.of(moved.state, moved.rules).npcs) == ["sacerdote"]
    assert [n.id for n in CampaignView.of(moved.campaign, moved.state).npcs] == ["sacerdote"]


def test_a_hidden_event_stays_hidden_if_the_npc_moves_afterwards(tmp_path):
    base = new_game(CAMPAIGN_PATH, tmp_path / "p.json", seed=7)
    state, _ = execute(base, 'entrar bia "Bia"')
    state, _ = execute(state, 'ferir sacerdote 2 "a"')  # o sacerdote está nas ruínas
    state, _ = execute(state, 'ferir ferreiro 1 "b"')  # o ferreiro está na vila, com o grupo
    npcs = dict(state.state.npcs)
    npcs["sacerdote"] = npcs["sacerdote"].model_copy(update={"location_id": "vila"})
    moved = state.state.model_copy(update={"npcs": npcs})  # um dia NPCs poderão andar
    damages = [i for i, e in enumerate(moved.events) if e.kind == "damage"]
    assert hidden_events(moved, state.campaign) == {damages[0]}  # o evento guardou onde ele estava


def test_an_old_event_without_the_recorded_location_uses_the_current_one(tmp_path):
    base = new_game(CAMPAIGN_PATH, tmp_path / "p.json", seed=7)
    state, _ = execute(base, 'entrar bia "Bia"')
    state, _ = execute(state, 'ferir sacerdote 2 "a"')
    events = []
    for event in state.state.events:
        data = {k: v for k, v in event.data.items() if k != "npc_locations"}
        events.append(event.model_copy(update={"data": data}))
    old = state.state.model_copy(update={"events": events})
    damage = next(i for i, e in enumerate(old.events) if e.kind == "damage")
    assert hidden_events(old, state.campaign) == {damage}
