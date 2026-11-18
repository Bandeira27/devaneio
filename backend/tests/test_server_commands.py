"""Comandos pela mesa: papel, dono do personagem, revisão e uma ação principal por turno."""

import threading
from itertools import count

import pytest

from conftest import CAMPAIGN_PATH, open_for_play
from devaneio.engine import GameStatus
from devaneio.server import ApiFailure, Catalog, Storage, TableService
from devaneio.server.models import CommandRequest, CreateTableRequest, JoinRequest

TOKENS = count(1)


class Desk:
    """Uma mesa com anfitrião; ``cmd`` busca a revisão atual quando não é dada."""

    def __init__(self, service, created):
        self.service = service
        self.id = created.table_id
        self.host = created.host_token

    def join(self, name):
        joined = self.service.join_table(self.id, JoinRequest(invite_code="convite", name=name))
        return joined.token

    def view(self, token):
        return self.service.get_table(self.id, token)

    def cmd(self, token, line, *, revision=None):
        if revision is None:
            revision = self.view(token).revision
        return self.service.run_command(
            self.id, token, CommandRequest(line=line, revision=revision)
        )

    def refused(self, token, line, *, revision=None):
        with pytest.raises(ApiFailure) as info:
            self.cmd(token, line, revision=revision)
        return info.value

    def raw(self):
        return self.service.storage.path_for(self.id).read_text(encoding="utf-8")

    def player(self, name, character=None):
        """Jogador que já entrou com um personagem (``id`` do personagem em minúsculas)."""
        token = self.join(name)
        character = character or name.lower()
        self.cmd(token, f'entrar {character} "{name}"')
        return token


@pytest.fixture
def desk(tmp_path):
    service = TableService(
        Catalog(CAMPAIGN_PATH.parent),
        Storage(tmp_path / "mesas", max_tables=10),
        token_source=lambda: f"token-{next(TOKENS)}",
        invite_source=lambda: "convite",
    )
    created = service.create_table(
        CreateTableRequest(campaign_id="sombra-do-vale", host_name="Ana", seed=7)
    )
    open_for_play(service, created.table_id)
    return Desk(service, created)


# --- entrar -------------------------------------------------------------------------


def test_a_player_enters_with_one_character_and_it_is_linked_to_them(desk):
    bia = desk.join("Bia")
    result = desk.cmd(bia, 'entrar bia "Bia" FOR=3')
    assert [e.kind for e in result.events] == ["character_joined"]
    assert "Bia entra na aventura" in result.text
    players = {p.id: p.character_ids for p in desk.view(bia).players}
    assert players == {"p1": [], "p2": ["bia"]}
    assert desk.view(bia).state.characters["bia"].name == "Bia"


def test_a_player_cannot_enter_twice_but_the_host_can(desk):
    bia = desk.player("Bia")
    before = desk.raw()
    error = desk.refused(bia, 'entrar bia2 "Outra"')
    assert (error.status, error.code) == (409, "character_limit")
    assert desk.raw() == before
    desk.cmd(desk.host, 'entrar ana "Ana"')
    desk.cmd(desk.host, 'entrar aliado "Aliado"')
    assert [p.character_ids for p in desk.view(desk.host).players] == [["ana", "aliado"], ["bia"]]


def test_entering_with_the_id_of_an_npc_is_refused(desk):
    before = desk.raw()
    error = desk.refused(desk.host, 'entrar ferreiro "Falso Bram"')
    assert (error.status, error.code) == (422, "command_refused")
    assert "já é o id de um NPC" in error.message
    assert desk.raw() == before


# --- quem age -----------------------------------------------------------------------


def test_a_player_without_a_character_cannot_act_for_someone_elses(desk):
    """Sem prefixo, o motor agiria pelo único personagem da partida, que é de outro."""
    desk.cmd(desk.host, 'entrar ana "Ana"')
    caio = desk.join("Caio")
    before = desk.raw()
    for line in ("testar lutar normal", "ana: testar lutar normal", "ir floresta"):
        error = desk.refused(caio, line)
        assert (error.status, error.code) == (403, "no_character")
    assert desk.raw() == before


def test_a_player_acts_only_for_their_own_character(desk):
    desk.cmd(desk.host, 'entrar ana "Ana"')
    bia = desk.player("Bia")
    before = desk.raw()
    error = desk.refused(bia, "ana: testar lutar normal")
    assert (error.status, error.code) == (403, "forbidden")
    assert desk.raw() == before
    result = desk.cmd(bia, "bia: testar lutar normal")
    assert [e.kind for e in result.events] == ["check"]
    assert "Bia" in result.events[0].text
    assert desk.view(bia).acted == {"bia": 0}


def test_the_character_is_injected_when_the_player_names_none(desk):
    desk.cmd(desk.host, 'entrar ana "Ana"')
    bia = desk.player("Bia")
    result = desk.cmd(bia, "testar lutar normal")
    assert "Bia" in result.events[0].text
    assert "Ana" not in result.events[0].text


def test_a_second_prefix_cannot_change_the_actor(desk):
    desk.cmd(desk.host, 'entrar ana "Ana"')
    bia = desk.player("Bia")
    before = desk.raw()
    error = desk.refused(bia, "bia: ana: testar lutar normal")
    assert (error.status, error.code) == (422, "command_refused")
    assert "comando desconhecido 'ana:'" in error.message
    assert desk.raw() == before


def test_the_host_names_the_actor_unless_they_own_exactly_one_character(desk):
    bia = desk.player("Bia")
    error = desk.refused(desk.host, "testar lutar normal")
    assert (error.status, error.code) == (422, "actor_required")  # nenhum personagem do anfitrião
    result = desk.cmd(desk.host, "bia: testar lutar normal")  # o mestre age por qualquer um
    assert "Bia" in result.events[0].text
    assert result.turn_ended is True  # Bia era o único personagem: o turno 0 fechou
    desk.cmd(desk.host, 'entrar ana "Ana"')
    desk.cmd(desk.host, "testar lutar normal")  # um só personagem: sem prefixo
    assert desk.view(bia).acted == {"bia": 0, "ana": 1}


@pytest.mark.parametrize(
    "line",
    ["fim", "descansar", "ferir bia 3", "curar bia 3", "marco ativar x", "marcos", "log"],
)
def test_host_commands_are_refused_to_players(desk, line):
    bia = desk.player("Bia")
    before = desk.raw()
    error = desk.refused(bia, line)
    assert (error.status, error.code) == (403, "forbidden")
    assert "comando do anfitrião" in error.message
    assert desk.raw() == before


# --- alvos escondidos e limites do entrar ------------------------------------------


def test_a_player_cannot_attack_an_npc_in_another_location(desk):
    """O sacerdote está nas ruínas: para quem está na vila ele não existe, nem como alvo."""
    bia = desk.player("Bia")
    before = desk.raw()
    hidden = desk.refused(bia, "atacar punhos sacerdote")
    missing = desk.refused(bia, "atacar punhos ninguem")
    assert (hidden.status, hidden.code) == (422, "command_refused")
    assert hidden.message == "alvo 'sacerdote' não está na partida"
    assert missing.message == "alvo 'ninguem' não está na partida"  # a mesma resposta
    assert desk.raw() == before  # nem ferido, nem gastou a ação
    assert desk.view(bia).acted == {}


def test_a_player_can_attack_who_is_in_the_same_location(desk):
    bia = desk.player("Bia")
    result = desk.cmd(bia, "atacar punhos ferreiro")
    assert result.events[0].kind == "check"


def test_the_host_can_attack_across_locations(desk):
    desk.player("Bia")
    result = desk.cmd(desk.host, "bia: atacar punhos sacerdote")
    assert result.events[0].kind == "check"
    assert "Bia" in result.events[0].text


@pytest.mark.parametrize(
    "line",
    [
        "entrar " + "x" * 41 + ' "Bia"',
        'entrar bia "' + "B" * 41 + '"',
        "entrar bia Bia " + " ".join(f"+i{n}" for n in range(30)),
    ],
    ids=["id-longo", "nome-longo", "itens-demais"],
)
def test_entering_has_size_limits(desk, line):
    bia = desk.join("Bia")
    before = desk.raw()
    error = desk.refused(bia, line)
    assert (error.status, error.code) == (422, "command_refused")
    assert "entrar aceita até" in error.message
    assert desk.raw() == before


def test_a_fallen_character_cannot_act_until_healed(desk):
    desk.cmd(desk.host, 'entrar ana "Ana"')
    bia = desk.player("Bia")
    desk.cmd(desk.host, "ferir bia 99")
    before = desk.raw()
    error = desk.refused(bia, "testar lutar normal")
    assert (error.status, error.code) == (422, "command_refused")
    assert "Bia está fora de combate e não pode agir" in error.message
    assert desk.raw() == before
    assert desk.view(bia).acted == {}  # recusa não gasta a ação
    desk.cmd(desk.host, "curar bia 5")
    assert desk.cmd(bia, "testar lutar normal").events[0].kind == "check"


# --- revisão, turno, fim da partida -------------------------------------------------


def test_a_stale_revision_is_refused_with_the_current_one(desk):
    bia = desk.player("Bia")
    seen = desk.view(bia).revision
    desk.cmd(desk.host, "ferir bia 1")  # a mesa andou
    before = desk.raw()
    error = desk.refused(bia, "testar lutar normal", revision=seen)
    assert (error.status, error.code) == (409, "stale_revision")
    assert f"revisão {seen + 1}" in error.message
    assert desk.raw() == before
    assert desk.cmd(bia, "testar lutar normal", revision=seen + 1).revision > seen + 1


def test_one_main_action_per_character_per_turn(desk):
    desk.cmd(desk.host, 'entrar ana "Ana"')
    bia = desk.player("Bia")
    desk.cmd(bia, "testar lutar normal")
    before = desk.raw()
    error = desk.refused(bia, "atacar punhos ferreiro")
    assert (error.status, error.code) == (409, "already_acted")
    assert desk.raw() == before
    desk.cmd(bia, "olhar")  # consulta não gasta a ação
    desk.cmd(bia, "ficha")


def test_the_turn_ends_by_itself_when_every_character_has_acted(desk):
    desk.cmd(desk.host, 'entrar ana "Ana"')
    bia = desk.player("Bia")
    first = desk.cmd(bia, "testar lutar normal")
    assert first.turn_ended is False
    assert desk.view(desk.host).state.turn == 0
    second = desk.cmd(desk.host, "testar lutar normal")
    assert second.turn_ended is True
    assert [e.kind for e in second.events][-2:] == ["director", "turn_end"]
    assert "Fim do turno 0" in second.text
    assert desk.view(desk.host).state.turn == 1
    desk.cmd(bia, "testar lutar normal")  # no turno novo, todos podem agir de novo


def test_a_fallen_character_does_not_hold_the_turn(desk):
    desk.cmd(desk.host, 'entrar ana "Ana"')
    desk.player("Bia")
    desk.cmd(desk.host, "ferir bia 99")
    result = desk.cmd(desk.host, "testar lutar normal")
    assert result.turn_ended is True
    assert result.status is GameStatus.ACTIVE


def test_the_host_can_end_the_turn_early_and_acted_resets(desk):
    bia = desk.player("Bia")
    desk.cmd(desk.host, 'entrar ana "Ana"')
    desk.cmd(bia, "testar lutar normal")
    desk.cmd(desk.host, "fim")
    assert desk.view(bia).state.turn == 1
    desk.cmd(bia, "testar lutar normal")


def test_a_finished_game_refuses_everything_but_reading(desk):
    desk.cmd(desk.host, 'entrar ana "Ana"')
    bia = desk.player("Bia")
    desk.cmd(desk.host, "ferir ana 99")
    final = desk.cmd(desk.host, "ferir bia 99")
    assert final.status is GameStatus.LOST
    for token, line in (
        (bia, "testar lutar normal"),
        (desk.host, "fim"),
        (desk.host, "curar ana 3"),
    ):
        error = desk.refused(token, line)
        assert (error.status, error.code) == (409, "game_over")
    assert "Turno" in desk.cmd(bia, "olhar").text
    assert desk.view(bia).status is GameStatus.LOST


def test_an_action_that_wins_the_game_does_not_try_to_close_the_turn(desk):
    bia = desk.join("Bia")
    desk.cmd(bia, 'entrar bia "Bia" FOR=5')
    desk.cmd(bia, "ir floresta")  # único personagem: cada ação fecha o turno sozinha
    desk.cmd(bia, "ir ruinas")
    desk.cmd(desk.host, "marco concluir pista")
    desk.cmd(desk.host, "ferir sacerdote 11")  # sobra 1 de hp
    result = desk.cmd(bia, "atacar punhos sacerdote")  # semente 7: o primeiro ataque acerta
    assert result.status is GameStatus.WON
    assert result.turn_ended is False
    assert result.events[-1].kind != "turn_end"
    assert desk.view(bia).status is GameStatus.WON


def test_the_host_spending_a_players_action_leaves_the_player_with_already_acted(desk):
    desk.cmd(desk.host, 'entrar ana "Ana"')
    bia = desk.player("Bia")
    desk.cmd(desk.host, "bia: testar lutar normal")
    before = desk.raw()
    error = desk.refused(bia, "testar lutar normal")
    assert (error.status, error.code) == (409, "already_acted")
    assert desk.raw() == before
    assert desk.view(bia).acted == {"bia": 0}


def test_a_fallen_target_leaves_the_turn_to_those_still_standing(desk):
    """Documenta o comportamento: atacar o personagem de outro jogador vale (decisão do dono);
    quem cai a hp 0 sai dos elegíveis, e o turno fecha sem ele ter agido."""
    bia = desk.player("Bia")
    caio = desk.join("Caio")
    desk.cmd(caio, 'entrar caio "Caio" FOR=5')
    desk.cmd(desk.host, "ferir bia 9")
    result = desk.cmd(caio, "atacar punhos bia")  # semente 7: acerta e derruba
    assert desk.view(bia).state.characters["bia"].hp == 0
    assert result.turn_ended is True
    assert desk.view(bia).state.turn == 1
    assert "bia" not in desk.view(bia).acted  # nunca agiu no turno 0


def test_a_command_the_game_does_not_know_does_not_need_a_fresh_revision(desk):
    bia = desk.player("Bia")
    error = desk.refused(bia, "dançar", revision=999)
    assert (error.status, error.code) == (422, "command_refused")  # e não stale_revision


def test_reading_works_with_a_stale_revision(desk):
    bia = desk.player("Bia")
    assert "Turno" in desk.cmd(bia, "olhar", revision=0).text


def test_the_fullwidth_spelling_of_a_host_command_is_still_a_host_command(desk):
    bia = desk.player("Bia")
    before = desk.raw()
    error = desk.refused(bia, "".join(chr(0xFF00 + ord(c) - 0x20) for c in "fim"))
    assert (error.status, error.code) == (403, "forbidden")
    assert desk.raw() == before


@pytest.mark.parametrize("line", ["atacar", "atacar punhos"])
def test_an_attack_without_target_gets_the_usage_error_from_the_game(desk, line):
    bia = desk.player("Bia")
    before = desk.raw()
    error = desk.refused(bia, line)
    assert (error.status, error.code) == (422, "command_refused")
    assert "uso: atacar" in error.message
    assert desk.raw() == before
    assert desk.view(bia).acted == {}


def test_entering_with_a_bad_attribute_links_no_character_and_writes_nothing(desk):
    bia = desk.join("Bia")
    before = desk.raw()
    error = desk.refused(bia, 'entrar bia "Bia" FOR=x')
    assert (error.status, error.code) == (422, "command_refused")
    assert "atributo inválido" in error.message
    assert desk.raw() == before
    assert [p.character_ids for p in desk.view(bia).players] == [[], []]
    desk.cmd(bia, 'entrar bia "Bia"')  # nada foi gasto: pode tentar de novo


def test_ficha_without_a_character_does_not_pick_one_for_the_player(desk):
    """Sem personagem, `ficha` segue sem prefixo e o motor decide: o único personagem da
    partida (que é público no estado do jogador) ou o erro de uso quando são vários."""
    caio = desk.join("Caio")
    error = desk.refused(caio, "ficha")
    assert error.code == "command_refused"
    assert "nenhum personagem" in error.message
    desk.cmd(desk.host, 'entrar ana "Ana"')
    assert desk.cmd(caio, "ficha").text.startswith("Ana (ana)")
    desk.cmd(desk.host, 'entrar aliado "Aliado"')
    error = desk.refused(caio, "ficha")
    assert error.code == "command_refused"
    assert "prefixe o comando" in error.message


# --- leitura ------------------------------------------------------------------------


def test_reading_never_writes_the_file(desk):
    bia = desk.player("Bia")
    before = desk.raw()
    for line in ("olhar", "ficha", "ajuda"):
        desk.cmd(bia, line)
    assert desk.raw() == before


def test_ficha_without_an_id_shows_the_players_own_sheet(desk):
    desk.cmd(desk.host, 'entrar ana "Ana"')
    bia = desk.player("Bia")
    assert desk.cmd(bia, "ficha").text.startswith("Bia (bia)")
    assert desk.cmd(bia, "ficha ana").text.startswith("Ana (ana)")


def test_players_do_not_see_pending_beats_through_marcos_or_olhar(desk):
    bia = desk.player("Bia")
    assert "Confronto" not in desk.cmd(bia, "olhar").text
    assert "Confronto" in desk.cmd(desk.host, "marcos").text


def test_unknown_commands_are_refused_as_the_game_refuses_them(desk):
    bia = desk.player("Bia")
    error = desk.refused(bia, "dançar")
    assert (error.status, error.code) == (422, "command_refused")
    assert "comando desconhecido 'dançar'" in error.message


def test_a_refused_game_command_is_a_422_and_does_not_spend_the_action(desk):
    bia = desk.player("Bia")
    error = desk.refused(bia, "testar lutar impossivel")
    assert error.status == 422
    assert desk.view(bia).acted == {}
    desk.cmd(bia, "testar lutar normal")


# --- eventos ------------------------------------------------------------------------


def test_events_come_with_prose_and_without_data(desk):
    bia = desk.player("Bia")
    desk.cmd(bia, "testar lutar normal")
    everything = desk.service.get_events(desk.id, bia, 0)
    assert everything.revision == len(everything.events)
    assert [e.index for e in everything.events] == list(range(everything.revision))
    assert everything.events[0].kind == "beat_activated"
    assert all(e.prose for e in everything.events)
    assert "data" not in everything.events[0].model_dump()
    tail = desk.service.get_events(desk.id, bia, 2)
    assert [e.index for e in tail.events] == list(range(2, everything.revision))
    assert desk.service.get_events(desk.id, bia, everything.revision).events == []
    assert desk.service.get_events(desk.id, bia, 999).events == []


def test_the_prose_of_an_event_is_the_same_for_every_reader(desk):
    bia = desk.player("Bia")
    desk.cmd(bia, "testar lutar normal")
    as_player = desk.service.get_events(desk.id, bia, 0)
    as_host = desk.service.get_events(desk.id, desk.host, 0)
    assert as_player == as_host


@pytest.mark.parametrize("token", [None, "token-errado"])
def test_commands_and_events_need_a_valid_token(desk, token):
    request = CommandRequest(line="olhar", revision=0)
    with pytest.raises(ApiFailure) as commands:
        desk.service.run_command(desk.id, token, request)
    with pytest.raises(ApiFailure) as events:
        desk.service.get_events(desk.id, token, 0)
    assert commands.value.status == events.value.status == 401


def test_a_token_from_another_table_is_not_valid_here(desk):
    other = desk.service.create_table(
        CreateTableRequest(campaign_id="sombra-do-vale", host_name="Zé", seed=7)
    )
    open_for_play(desk.service, other.table_id)
    request = CommandRequest(line="olhar", revision=0)
    with pytest.raises(ApiFailure, match="token inválido") as commands:
        desk.service.run_command(desk.id, other.host_token, request)
    with pytest.raises(ApiFailure, match="token inválido") as events:
        desk.service.get_events(desk.id, other.host_token, 0)
    assert commands.value.status == events.value.status == 401


def test_commands_on_an_unknown_table_are_404(desk):
    with pytest.raises(ApiFailure) as info:
        desk.service.run_command(
            "0123456789abcdef", desk.host, CommandRequest(line="olhar", revision=0)
        )
    assert info.value.status == 404


def test_two_simultaneous_commands_for_one_character_apply_once(desk):
    bia = desk.player("Bia")
    revision = desk.view(bia).revision
    workers = 6
    start = threading.Barrier(workers)  # todos disparam juntos, sem sleep
    outcomes = []

    def act():
        start.wait()
        try:
            desk.cmd(bia, "testar lutar normal", revision=revision)
            outcomes.append("ok")
        except ApiFailure as exc:
            outcomes.append(exc.code)

    threads = [threading.Thread(target=act) for _ in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(outcomes) == workers  # nenhuma thread morreu por outra exceção
    assert outcomes.count("ok") == 1
    assert set(outcomes) <= {"ok", "stale_revision", "already_acted"}
    checks = [e for e in desk.service.get_events(desk.id, bia, 0).events if e.kind == "check"]
    assert len(checks) == 1
