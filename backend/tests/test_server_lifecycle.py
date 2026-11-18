"""Fases da mesa pelo servidor: sala de espera, iniciar, pausar, retomar e encerrar."""

from itertools import count

import pytest

from conftest import CAMPAIGN_PATH
from devaneio.server import ApiFailure, Catalog, Storage, TableService
from devaneio.server.models import (
    CommandRequest,
    CreateTableRequest,
    JoinRequest,
    LifecycleRequest,
)

TOKENS = count(1)


class Clock:
    """Relógio do servidor que o teste move à mão."""

    def __init__(self):
        self.now = 1_000.0

    def __call__(self):
        return self.now


class Room:
    """Uma mesa recém-criada (sala de espera) com o anfitrião Ana."""

    def __init__(self, tmp_path):
        self.clock = Clock()
        self.service = TableService(
            Catalog(CAMPAIGN_PATH.parent),
            Storage(tmp_path / "mesas", max_tables=10),
            token_source=lambda: f"token-{next(TOKENS)}",
            invite_source=lambda: "convite",
            clock=self.clock,
        )
        created = self.service.create_table(
            CreateTableRequest(campaign_id="sombra-do-vale", host_name="Ana", seed=7)
        )
        self.id, self.host = created.table_id, created.host_token

    def view(self, token):
        return self.service.get_table(self.id, token)

    def cmd(self, token, line):
        revision = self.view(token).revision
        return self.service.run_command(
            self.id, token, CommandRequest(line=line, revision=revision)
        )

    def refused(self, token, line):
        with pytest.raises(ApiFailure) as info:
            self.cmd(token, line)
        return info.value

    def join(self, name):
        joined = self.service.join_table(self.id, JoinRequest(invite_code="convite", name=name))
        return joined.token

    def phase(self, token, action, revision=None):
        if revision is None:
            revision = self.view(self.host).revision
        return self.service.set_phase(
            self.id, token, LifecycleRequest(action=action, revision=revision)
        )

    def refused_phase(self, token, action, revision=None):
        with pytest.raises(ApiFailure) as info:
            self.phase(token, action, revision)
        return info.value


@pytest.fixture
def room(tmp_path):
    return Room(tmp_path)


@pytest.fixture
def started(room):
    """Anfitrião e Bia com personagem, e a partida iniciada."""
    room.bia = room.join("Bia")
    room.cmd(room.bia, 'entrar bia "Bia"')
    room.cmd(room.host, 'entrar ana "Ana"')
    room.phase(room.host, "start")
    return room


def test_a_new_table_waits_in_the_lobby_with_no_story_yet(room):
    view = room.view(room.host)
    assert (view.phase, view.revision, view.elapsed_seconds) == ("lobby", 0, 0)
    assert view.state.events == []


def test_guests_join_and_create_characters_in_the_lobby_without_starting_the_story(room):
    bia = room.join("Bia")
    result = room.cmd(bia, 'entrar bia "Bia"')
    assert [e.kind for e in result.events] == ["character_joined"]  # sem "marco ativado"
    view = room.view(room.host)
    assert view.phase == "lobby"
    assert [p.character_ids for p in view.players] == [[], ["bia"]]


def test_the_lobby_reads_but_does_not_act(room):
    bia = room.join("Bia")
    room.cmd(bia, 'entrar bia "Bia"')
    room.cmd(room.host, "olhar")  # ler pode
    for who, line in ((bia, "ir floresta"), (bia, "testar lutar normal"), (room.host, "fim")):
        error = room.refused(who, line)
        assert (error.status, error.code) == (409, "not_started")


def test_only_the_host_changes_the_phase(room):
    bia = room.join("Bia")
    room.cmd(bia, 'entrar bia "Bia"')
    error = room.refused_phase(bia, "start")
    assert (error.status, error.code) == (403, "forbidden")
    with pytest.raises(ApiFailure) as info:
        room.service.set_phase(room.id, None, LifecycleRequest(action="start", revision=0))
    assert (info.value.status, info.value.code) == (401, "unauthorized")
    with pytest.raises(ApiFailure) as info:
        room.service.set_phase(
            "0123456789abcdef", room.host, LifecycleRequest(action="start", revision=0)
        )
    assert (info.value.status, info.value.code) == (404, "table_not_found")
    assert room.view(room.host).phase == "lobby"


def test_starting_needs_a_character(room):
    error = room.refused_phase(room.host, "start")
    assert (error.status, error.code) == (409, "no_characters")
    assert room.view(room.host).phase == "lobby"


def test_a_stale_revision_is_refused(room):
    room.cmd(room.host, 'entrar ana "Ana"')
    error = room.refused_phase(room.host, "start", revision=0)
    assert (error.status, error.code) == (409, "stale_revision")


def test_starting_opens_the_story_for_everyone(started):
    host_view = started.view(started.host)
    assert (host_view.phase, host_view.elapsed_seconds) == ("running", 0)
    kinds = [e.kind for e in started.service.get_events(started.id, started.bia, 0).events]
    assert kinds[-2:] == ["table_started", "beat_activated"]
    result = started.cmd(started.bia, "ir floresta")  # agora se pode agir
    assert result.events


def test_the_clock_counts_only_the_time_the_game_runs(started):
    started.clock.now += 90
    assert started.view(started.bia).elapsed_seconds == 90
    started.phase(started.host, "pause")
    started.clock.now += 5_000  # a pausa não conta
    assert started.view(started.bia).elapsed_seconds == 90
    started.phase(started.host, "resume")
    started.clock.now += 30
    assert started.view(started.host).elapsed_seconds == 120
    started.phase(started.host, "end")
    started.clock.now += 5_000
    assert started.view(started.host).elapsed_seconds == 120


def test_a_pause_stops_the_players_and_lets_the_host_go_on(started):
    started.phase(started.host, "pause")
    started.cmd(started.bia, "olhar")  # ler pode
    error = started.refused(started.bia, "ir floresta")
    assert (error.status, error.code) == (409, "paused")
    started.cmd(started.host, "ir floresta")  # o anfitrião continua
    started.phase(started.host, "resume")
    started.cmd(started.bia, "ir vila")


def test_pausing_and_resuming_reach_the_players_through_the_log(started):
    seen = started.view(started.bia).revision
    started.phase(started.host, "pause")
    news = started.service.get_events(started.id, started.bia, seen).events
    assert [(e.kind, e.text) for e in news] == [("table_paused", "O anfitrião pausou a partida.")]
    assert started.view(started.bia).phase == "paused"


def test_ending_is_final_and_leaves_only_reading(started):
    started.phase(started.host, "end")
    assert started.view(started.bia).phase == "ended"
    for who in (started.bia, started.host):
        started.cmd(who, "olhar")
        error = started.refused(who, "ir floresta")
        assert (error.status, error.code) == (409, "ended")
    for action in ("start", "pause", "resume", "end"):
        error = started.refused_phase(started.host, action)
        assert (error.status, error.code) == (409, "ended")
    with pytest.raises(ApiFailure) as info:
        started.join("Caio")
    assert (info.value.status, info.value.code) == (409, "table_ended")


def test_transitions_that_make_no_sense_are_refused(started):
    for action in ("start", "resume"):
        error = started.refused_phase(started.host, action)
        assert (error.status, error.code) == (409, "invalid_transition")


def test_the_phase_survives_a_reload_from_disk(started):
    started.clock.now += 40
    started.phase(started.host, "pause")
    again = TableService(
        started.service.catalog,
        started.service.storage,
        clock=started.clock,
    )
    view = again.get_table(started.id, started.host)
    assert (view.phase, view.elapsed_seconds) == ("paused", 40)
