"""O que um jogador comum não vê do log: eventos sobre NPC que o grupo não via na hora."""

import threading
import time
from itertools import count

import pytest

from conftest import CAMPAIGN_PATH
from devaneio.game import execute, new_game
from devaneio.server import ApiFailure, Catalog, Storage, TableService
from devaneio.server.models import CommandRequest, CreateTableRequest, JoinRequest
from devaneio.server.turns import hidden_events

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
        return self.service.get_events(self.id, token, since, wait)


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
