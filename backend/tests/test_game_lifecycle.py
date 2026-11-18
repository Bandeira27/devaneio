"""Ciclo de vida da mesa: sala de espera, em andamento, pausada e encerrada."""

from dataclasses import replace

import pytest

from conftest import CAMPAIGN_PATH
from devaneio.game import LifecycleError, Player, TableMeta, change_phase, execute, new_game
from devaneio.schema import BeatStatus


def lobby_session(tmp_path, *, with_character=True):
    session = new_game(CAMPAIGN_PATH, tmp_path / "mesa.json", seed=7, start=False)
    host = Player(name="Ana", role="host", token_hash="x" * 64)
    table = TableMeta(invite_hash="y" * 64, players={"p1": host}, phase="lobby")
    session = replace(session, table=table)
    if with_character:
        updated, _ = execute(session, 'entrar ana "Ana"')
        session = replace(updated, table=table)
    return session, table


def test_a_new_game_can_wait_for_the_start(tmp_path):
    waiting = new_game(CAMPAIGN_PATH, tmp_path / "a.json", seed=7, start=False)
    assert waiting.state.events == []
    assert set(waiting.state.beats.values()) == {BeatStatus.PENDING}
    started = new_game(CAMPAIGN_PATH, tmp_path / "b.json", seed=7)
    assert [e.kind for e in started.state.events] == ["beat_activated"]  # a abertura de sempre


def test_the_default_phase_keeps_tables_saved_before_the_lobby_running():
    assert TableMeta(invite_hash="y" * 64).phase == "running"


def test_starting_needs_a_character(tmp_path):
    session, table = lobby_session(tmp_path, with_character=False)
    with pytest.raises(LifecycleError) as info:
        change_phase(session, table, "start", now=100.0)
    assert info.value.code == "no_characters"


def test_starting_runs_the_opening_after_the_start_event_and_opens_the_clock(tmp_path):
    session, table = lobby_session(tmp_path)
    before = list(session.state.events)
    started, new_table = change_phase(session, table, "start", now=100.0)
    kinds = [e.kind for e in started.state.events]
    assert kinds[: len(before)] == [e.kind for e in before]
    assert kinds[len(before) :] == ["table_started", "beat_activated"]
    assert started.state.events[len(before)].text == "A partida começou."
    assert (new_table.phase, new_table.started_at, new_table.resumed_at) == (
        "running",
        100.0,
        100.0,
    )
    assert started.table == new_table
    # nada da entrada foi mexido
    assert session.state.events == before
    assert table.phase == "lobby"


def test_the_clock_runs_only_while_running(tmp_path):
    session, table = lobby_session(tmp_path)
    session, table = change_phase(session, table, "start", now=100.0)
    assert table.elapsed(160.0) == 60
    session, table = change_phase(session, table, "pause", now=160.0)
    assert (table.phase, table.played_seconds, table.resumed_at) == ("paused", 60.0, None)
    assert table.elapsed(10_000.0) == 60  # parada: a pausa não conta
    session, table = change_phase(session, table, "resume", now=500.0)
    assert table.elapsed(530.0) == 90
    session, table = change_phase(session, table, "end", now=560.0)
    assert (table.phase, table.played_seconds, table.resumed_at) == ("ended", 120.0, None)
    assert table.elapsed(99_999.0) == 120


def test_ending_while_paused_keeps_the_time_played(tmp_path):
    session, table = lobby_session(tmp_path)
    session, table = change_phase(session, table, "start", now=0.0)
    session, table = change_phase(session, table, "pause", now=30.0)
    session, table = change_phase(session, table, "end", now=999.0)
    assert (table.phase, table.played_seconds) == ("ended", 30.0)


def test_each_transition_leaves_a_line_in_the_log(tmp_path):
    session, table = lobby_session(tmp_path)
    session, table = change_phase(session, table, "start", now=0.0)
    for action, kind, text in (
        ("pause", "table_paused", "O anfitrião pausou a partida."),
        ("resume", "table_resumed", "O anfitrião retomou a partida."),
        ("end", "table_ended", "O anfitrião encerrou a partida."),
    ):
        session, table = change_phase(session, table, action, now=1.0)
        assert (session.state.events[-1].kind, session.state.events[-1].text) == (kind, text)


def test_the_lobby_can_be_ended_without_starting(tmp_path):
    session, table = lobby_session(tmp_path, with_character=False)
    _, new_table = change_phase(session, table, "end", now=5.0)
    assert (new_table.phase, new_table.played_seconds) == ("ended", 0.0)


@pytest.mark.parametrize(
    ("phase", "action", "code"),
    [
        ("lobby", "pause", "invalid_transition"),
        ("lobby", "resume", "invalid_transition"),
        ("running", "start", "invalid_transition"),
        ("running", "resume", "invalid_transition"),
        ("paused", "pause", "invalid_transition"),
        ("paused", "start", "invalid_transition"),
        ("ended", "start", "ended"),
        ("ended", "pause", "ended"),
        ("ended", "resume", "ended"),
        ("ended", "end", "ended"),
    ],
)
def test_transitions_that_make_no_sense_are_refused(tmp_path, phase, action, code):
    session, table = lobby_session(tmp_path)
    table = table.model_copy(update={"phase": phase})
    with pytest.raises(LifecycleError) as info:
        change_phase(session, table, action, now=1.0)
    assert info.value.code == code
