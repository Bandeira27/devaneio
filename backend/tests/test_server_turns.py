"""Funções de política da mesa testadas direto: quem pode, com qual linha, e o turno."""

import pytest

from conftest import CAMPAIGN_PATH
from devaneio.game import CommandError, Player, TableMeta, execute, new_game, parse_line
from devaneio.server import ApiFailure
from devaneio.server.turns import (
    authorize_proposal,
    check_say,
    check_turn,
    resolve,
    speaker,
)


def player(role="player", *characters):
    return Player.model_validate(
        {"name": "P", "role": role, "token_hash": "h", "character_ids": list(characters)}
    )


@pytest.fixture
def session(tmp_path):
    base = new_game(CAMPAIGN_PATH, tmp_path / "p.json", seed=7)
    base, _ = execute(base, 'entrar bia "Bia"')
    base, _ = execute(base, 'entrar ana "Ana"')
    return base


def table(acted=None):
    return TableMeta.model_validate({"invite_hash": "i", "acted": acted or {}})


# --- resolve ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "testar lutar normal",
        "TESTAR lutar normal",
        "bia: testar lutar normal",
        "  bia:   testar   lutar normal ",
        '"testar" lutar normal',
        "testar 'lutar' normal",
        "atacar punhos ferreiro",
        "ir floresta",
    ],
)
def test_the_rebuilt_line_reads_back_as_the_expected_actor_and_command(session, line):
    """Classificação e motor usam o mesmo analisador: a linha final tem o ator injetado e o
    mesmo comando (isto substitui uma guarda que nenhuma entrada alcança)."""
    plan = resolve(player("player", "bia"), line, session.state)
    assert plan.kind == "action"
    assert plan.actor == "bia"
    _, name, _ = parse_line(line)
    assert parse_line(plan.line)[:2] == ("bia", name)


def test_an_unknown_command_keeps_its_line_for_the_game_to_refuse(session):
    plan = resolve(player("player", "bia"), "dançar muito", session.state)
    assert (plan.kind, plan.actor, plan.line) == (None, "", "dançar muito")


def test_resolve_refuses_by_role_and_by_owner(session):
    with pytest.raises(ApiFailure) as role:
        resolve(player("player", "bia"), "fim", session.state)
    assert (role.value.status, role.value.code) == (403, "forbidden")
    with pytest.raises(ApiFailure) as owner:
        resolve(player("player", "bia"), "ana: testar lutar normal", session.state)
    assert (owner.value.status, owner.value.code) == (403, "forbidden")


def test_resolve_does_not_look_at_revision_or_turn(session):
    """Isso é do `check_turn`: um jogador que já agiu ainda "pode" no sentido da política."""
    assert resolve(player("player", "bia"), "testar lutar normal", session.state).actor == "bia"


# --- check_turn e check_say -------------------------------------------------------


def test_check_turn_wants_the_current_revision_for_commands_that_change_the_game(session):
    plan = resolve(player("player", "bia"), "testar lutar normal", session.state)
    current = len(session.state.events)
    check_turn(table(), session.state, plan, current)
    with pytest.raises(ApiFailure) as stale:
        check_turn(table(), session.state, plan, current - 1)
    assert (stale.value.status, stale.value.code) == (409, "stale_revision")
    assert f"revisão {current}" in stale.value.message
    read = resolve(player("player", "bia"), "olhar", session.state)
    check_turn(table(), session.state, read, 0)  # consulta não precisa de revisão fresca


def test_check_turn_allows_one_main_action_per_character_per_turn(session):
    plan = resolve(player("player", "bia"), "testar lutar normal", session.state)
    revision = len(session.state.events)
    check_turn(table({"bia": session.state.turn - 1}), session.state, plan, revision)
    with pytest.raises(ApiFailure) as acted:
        check_turn(table({"bia": session.state.turn}), session.state, plan, revision)
    assert (acted.value.status, acted.value.code) == (409, "already_acted")


def test_check_say_wants_revision_active_game_and_an_unspent_action(session):
    revision = len(session.state.events)
    check_say(table(), session.state, "bia", revision)
    for seen, acted, code in (
        (revision - 1, {}, "stale_revision"),
        (revision, {"bia": 0}, "already_acted"),
    ):
        with pytest.raises(ApiFailure) as info:
            check_say(table(acted), session.state, "bia", seen)
        assert info.value.code == code
    over, _ = execute(session, "ferir bia 99")
    over, _ = execute(over, "ferir ana 99")
    with pytest.raises(ApiFailure) as ended:
        check_say(table(), over.state, "bia", len(over.state.events))
    assert (ended.value.status, ended.value.code) == (409, "game_over")


# --- speaker e authorize_proposal -------------------------------------------------


def test_speaker_strips_a_known_prefix_and_keeps_other_colons(session):
    host = player("host", "ana", "bia")
    assert speaker(session.state, host, "ana: vou") == ("ana", "vou")
    assert speaker(session.state, player("player", "bia"), "digo: oi") == ("bia", "digo: oi")
    with pytest.raises(ApiFailure) as info:
        speaker(session.state, host, "vou sem dizer quem")
    assert info.value.code == "actor_required"


@pytest.mark.parametrize("line", ["bia: olhar", 'bia: entrar x "X"', "bia: dançar"])
def test_only_game_actions_exist_as_proposals(session, line):
    with pytest.raises(CommandError, match="não é uma ação que o mestre possa propor"):
        authorize_proposal(player("player", "bia"), session, line)


def test_a_proposal_follows_the_role_of_who_spoke(session):
    authorize_proposal(player("player", "bia"), session, "bia: testar lutar normal")
    with pytest.raises(CommandError, match="comando do anfitrião"):
        authorize_proposal(player("player", "bia"), session, "bia: descansar")
    authorize_proposal(player("host", "ana"), session, "ana: descansar")
