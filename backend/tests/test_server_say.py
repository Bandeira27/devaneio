"""Texto livre pela mesa: o LLM do anfitrião propõe, a política do jogador e o motor decidem."""

import json
import threading
import urllib.error
import urllib.request
from itertools import count

import pytest

from conftest import CAMPAIGN_PATH
from devaneio.engine import GameStatus
from devaneio.llm import LlmConfig
from devaneio.server import ApiFailure, Catalog, Storage, TableService
from devaneio.server.http import make_server
from devaneio.server.models import CommandRequest, CreateTableRequest, JoinRequest, SayRequest
from devaneio.server.storage import MAX_NARRATIONS
from fakes import FakeLlmServer

TOKENS = count(1)
PROPOSER_MARK = "APENAS com um objeto JSON"


def proposal(*actions, say=""):
    return json.dumps({"actions": list(actions), "say": say})


CHECK = {"kind": "check", "skill": "lutar", "difficulty": "normal"}
REST = {"kind": "rest"}
HIDDEN_ATTACK = {"kind": "attack", "weapon": "punhos", "target": "sacerdote"}


class Script:
    """O que o servidor de LLM falso responde: propostas em fila e a narração."""

    def __init__(self):
        self.proposals = []
        self.narration = "O vento muda de direção."
        self.narration_status = 200
        self.proposer_status = 200
        self.before_reply = None  # chamado no meio da chamada ao LLM (fora do lock da mesa)
        self.requests = []

    def respond(self, body):
        self.requests.append(body)
        system = body["messages"][0]["content"]
        if PROPOSER_MARK in system:
            if self.before_reply:
                self.before_reply()
            if self.proposer_status != 200:
                return self.proposer_status, "falhou"
            reply = self.proposals.pop(0) if self.proposals else proposal()
            return 200, reply
        return self.narration_status, self.narration

    def proposer_calls(self):
        return [r for r in self.requests if PROPOSER_MARK in r["messages"][0]["content"]]


@pytest.fixture
def script():
    return Script()


@pytest.fixture
def llm(script):
    with FakeLlmServer(script.respond) as server:
        yield server


@pytest.fixture
def service(tmp_path, llm):
    config = LlmConfig(base_url=llm.base_url, model="m-teste", api_key="chave-secreta")
    return TableService(
        Catalog(CAMPAIGN_PATH.parent),
        Storage(tmp_path / "mesas", max_tables=10),
        llm=config,
        token_source=lambda: f"token-{next(TOKENS)}",
        invite_source=lambda: "convite",
    )


class Desk:
    def __init__(self, service):
        self.service = service
        created = service.create_table(
            CreateTableRequest(campaign_id="sombra-do-vale", host_name="Ana", seed=7)
        )
        self.id, self.host = created.table_id, created.host_token

    def player(self, name):
        joined = self.service.join_table(self.id, JoinRequest(invite_code="convite", name=name))
        self.cmd(joined.token, f'entrar {name.lower()} "{name}"')
        return joined.token

    def revision(self, token):
        return self.service.get_table(self.id, token).revision

    def cmd(self, token, line):
        request = CommandRequest(line=line, revision=self.revision(token))
        return self.service.run_command(self.id, token, request)

    def say(self, token, text, *, revision=None):
        if revision is None:
            revision = self.revision(token)
        return self.service.say(self.id, token, SayRequest(text=text, revision=revision))

    def refused(self, token, text, *, revision=None):
        with pytest.raises(ApiFailure) as info:
            self.say(token, text, revision=revision)
        return info.value

    def raw(self):
        return self.service.storage.path_for(self.id).read_text(encoding="utf-8")

    def events(self, token, since=0):
        return self.service.get_events(self.id, token, since).events


@pytest.fixture
def desk(service):
    return Desk(service)


# --- o caminho feliz ----------------------------------------------------------------


def test_the_llm_proposes_and_the_engine_applies(desk, script):
    bia = desk.player("Bia")
    script.proposals.append(proposal(CHECK, say="Você respira fundo."))
    before = desk.revision(bia)
    result = desk.say(bia, "tento enfrentar o medo")
    assert result.say == "Você respira fundo."
    assert result.commands == ["testar lutar normal"]
    assert result.events[0].kind == "check"
    assert "Bia" in result.events[0].text
    assert result.revision == before + len(result.events)
    assert result.turn_ended is True  # Bia é a única com personagem: a ação dela fecha o turno
    assert desk.service.get_table(desk.id, bia).acted == {"bia": 0}  # registrada no turno 0


def test_the_whole_proposal_spends_one_main_action(desk, script):
    desk.cmd(desk.host, 'entrar ana "Ana"')
    bia = desk.player("Bia")
    script.proposals.append(proposal(CHECK, CHECK, CHECK))
    result = desk.say(bia, "tento três vezes")
    assert result.commands == ["testar lutar normal"] * 3
    assert desk.service.get_table(desk.id, bia).acted == {"bia": 0}
    error = desk.refused(bia, "e mais uma")
    assert (error.status, error.code) == (409, "already_acted")


def test_the_turn_closes_when_the_say_was_the_last_action(desk, script):
    bia = desk.player("Bia")
    script.proposals.append(proposal(CHECK))
    result = desk.say(bia, "tento")
    assert result.turn_ended is True
    assert [e.kind for e in result.events][-2:] == ["director", "turn_end"]


def test_a_proposal_without_actions_changes_nothing(desk, script):
    bia = desk.player("Bia")
    script.proposals.append(proposal(say="Bram acena com a cabeça."))
    before = desk.raw()
    result = desk.say(bia, "cumprimento o ferreiro")
    assert result.say == "Bram acena com a cabeça."
    assert result.events == []
    assert result.commands == []
    assert desk.raw() == before  # nada gravado, ação principal intacta
    assert desk.service.get_table(desk.id, bia).acted == {}
    assert len(script.requests) == 1  # e sem narração para o que não aconteceu


# --- a política vale para a proposta ------------------------------------------------


def test_the_llm_cannot_rest_for_a_player(desk, script):
    """`rest` encerra o turno de todos: é do anfitrião, e a proposta segue o papel de quem falou."""
    bia = desk.player("Bia")
    script.proposals += [proposal(REST), proposal(REST)]
    before = desk.raw()
    error = desk.refused(bia, "a gente descansa aqui")
    assert (error.status, error.code) == (422, "command_refused")
    assert "comando do anfitrião" in error.message
    assert desk.raw() == before
    second_attempt = script.proposer_calls()[1]["messages"][-1]["content"]
    assert "comando do anfitrião" in second_attempt  # a recusa voltou ao modelo como feedback


def test_the_llm_may_rest_for_the_host(desk, script):
    desk.cmd(desk.host, 'entrar ana "Ana"')
    desk.cmd(desk.host, "ferir ana 3")  # o motor só deixa descansar com alguém ferido
    script.proposals.append(proposal(REST))
    result = desk.say(desk.host, "acampamos")
    assert result.commands == ["descansar"]
    assert any(e.kind == "turn_end" for e in result.events)


def test_the_llm_cannot_attack_an_npc_the_player_does_not_see(desk, script):
    bia = desk.player("Bia")
    script.proposals += [proposal(HIDDEN_ATTACK), proposal(HIDDEN_ATTACK)]
    before = desk.raw()
    error = desk.refused(bia, "ataco o sacerdote")
    assert "alvo 'sacerdote' não está na partida" in error.message
    assert desk.raw() == before


def test_the_proposal_sees_the_session_advanced_by_its_own_moves(desk, script):
    """O sacerdote só aparece depois que o grupo chega às ruínas: a política julga cada ação
    sobre a sessão já avançada pelas anteriores."""
    bia = desk.player("Bia")
    walk = [{"kind": "move", "to": "floresta"}, {"kind": "move", "to": "ruinas"}]
    script.proposals.append(proposal(*walk, HIDDEN_ATTACK))
    result = desk.say(bia, "sigo até as ruínas e ataco o sacerdote")
    assert result.commands == ["ir floresta", "ir ruinas", "atacar punhos sacerdote"]
    texts = [e.text for e in result.events if e.kind == "move"]
    assert texts[-1] == "O grupo vai de Floresta Cinzenta para Ruínas do Templo."
    assert any(e.kind == "check" and e.text.startswith("Bia testa Lutar") for e in result.events)
    assert any(
        e.kind == "damage" and "Irmão Vael" in e.text for e in result.events
    )  # o contra-ataque


def test_a_player_may_attack_a_character_of_another_player(desk, script):
    desk.cmd(desk.host, 'entrar ana "Ana"')
    bia = desk.player("Bia")
    script.proposals.append(proposal({"kind": "attack", "weapon": "punhos", "target": "ana"}))
    result = desk.say(bia, "empurro a Ana")
    assert result.commands == ["atacar punhos ana"]
    assert result.events[0].kind == "check"
    assert result.events[0].text.startswith("Bia testa Lutar")


def test_a_proposal_that_is_not_json_twice_is_refused_and_changes_nothing(desk, script):
    bia = desk.player("Bia")
    script.proposals += ["isto não é json", "nem isto"]
    before = desk.raw()
    error = desk.refused(bia, "tento")
    assert (error.status, error.code) == (422, "command_refused")
    assert "o mestre (LLM) não propôs uma ação válida" in error.message
    assert len(script.proposer_calls()) == 2
    assert desk.raw() == before


def test_a_refusal_then_a_valid_second_try_is_applied(desk, script):
    bia = desk.player("Bia")
    script.proposals += [proposal(REST), proposal(CHECK)]
    result = desk.say(bia, "descanso e depois tento")
    assert result.commands == ["testar lutar normal"]


def test_the_speaker_is_the_players_own_character(desk, script):
    desk.cmd(desk.host, 'entrar ana "Ana"')
    bia = desk.player("Bia")
    script.proposals.append(proposal(CHECK))
    desk.say(bia, "tento")
    prompt = script.proposer_calls()[0]["messages"][1]["content"]
    assert "JOGADOR (Bia): tento" in prompt
    error = desk.refused(desk.player("Caio"), "ana: tento")
    assert (error.status, error.code) == (403, "forbidden")


def test_a_player_without_a_character_cannot_speak(desk):
    caio = desk.service.join_table(desk.id, JoinRequest(invite_code="convite", name="Caio")).token
    error = desk.refused(caio, "olá")
    assert (error.status, error.code) == (403, "no_character")


def test_the_host_names_the_speaker_when_they_own_none(desk):
    desk.player("Bia")
    error = desk.refused(desk.host, "olá")
    assert (error.status, error.code) == (422, "actor_required")


def test_a_host_with_two_characters_must_name_who_acts(desk, script):
    desk.cmd(desk.host, 'entrar ana "Ana"')
    desk.cmd(desk.host, 'entrar ze "Zé"')
    error = desk.refused(desk.host, "tento")
    assert (error.status, error.code) == (422, "actor_required")
    assert script.requests == []
    script.proposals.append(proposal(CHECK))
    result = desk.say(desk.host, "ze: tento")
    assert result.commands == ["testar lutar normal"]
    assert "Zé" in result.events[0].text
    assert desk.service.get_table(desk.id, desk.host).acted == {"ze": 0}
    assert "JOGADOR (Zé): tento" in script.proposer_calls()[0]["messages"][1]["content"]


# --- recusas antes de chamar o LLM --------------------------------------------------


def test_nothing_reaches_the_llm_when_the_table_refuses_first(desk, script):
    desk.cmd(desk.host, 'entrar ana "Ana"')  # com dois personagens, o turno não fecha sozinho
    bia = desk.player("Bia")
    seen = desk.revision(bia)
    desk.cmd(bia, "testar lutar normal")
    for revision, code in ((seen, "stale_revision"), (desk.revision(bia), "already_acted")):
        error = desk.refused(bia, "tento", revision=revision)
        assert (error.status, error.code) == (409, code)
    assert script.requests == []


def test_a_finished_game_refuses_before_the_llm(desk, script):
    desk.cmd(desk.host, 'entrar ana "Ana"')
    bia = desk.player("Bia")
    desk.cmd(desk.host, "ferir ana 99")
    desk.cmd(desk.host, "ferir bia 99")
    error = desk.refused(bia, "tento")
    assert (error.status, error.code) == (409, "game_over")
    assert script.requests == []


def test_without_llm_the_table_says_so(tmp_path):
    service = TableService(Catalog(CAMPAIGN_PATH.parent), Storage(tmp_path / "m", max_tables=2))
    desk = Desk(service)
    error = desk.refused(desk.host, "olá")
    assert (error.status, error.code) == (409, "llm_disabled")


@pytest.mark.parametrize("token", [None, "token-errado"])
def test_say_needs_a_valid_token(desk, script, token):
    with pytest.raises(ApiFailure) as info:
        desk.service.say(desk.id, token, SayRequest(text="oi", revision=0))
    assert info.value.status == 401
    assert script.requests == []


def test_say_on_an_unknown_table_is_404(desk):
    with pytest.raises(ApiFailure) as info:
        desk.service.say("0123456789abcdef", desk.host, SayRequest(text="oi", revision=0))
    assert info.value.status == 404


# --- o LLM falha, ou a mesa muda enquanto ele pensa ---------------------------------


def test_an_llm_outage_is_a_502_without_provider_details(desk, script, capsys):
    bia = desk.player("Bia")
    script.proposer_status = 500
    before = desk.raw()
    error = desk.refused(bia, "tento")
    assert (error.status, error.code) == (502, "llm_unavailable")
    assert "falhou" not in error.message
    assert "m-teste" not in error.message
    assert "o LLM falhou" in capsys.readouterr().err  # o detalhe vai ao operador
    assert desk.raw() == before


def test_a_command_during_the_llm_call_makes_the_say_stale_and_keeps_both_safe(desk, script):
    desk.cmd(desk.host, 'entrar ana "Ana"')
    bia = desk.player("Bia")
    script.proposals.append(proposal(CHECK))

    def host_acts_meanwhile():  # o lock da mesa está livre durante a chamada ao LLM
        desk.cmd(desk.host, "ferir bia 1")

    script.before_reply = host_acts_meanwhile
    error = desk.refused(bia, "tento")
    assert (error.status, error.code) == (409, "stale_revision")
    kinds = [e.kind for e in desk.events(bia)]
    assert kinds[-1] == "damage"  # o comando do anfitrião ficou; a tentativa se perdeu
    assert "check" not in kinds


def test_a_join_during_the_llm_call_makes_the_say_stale_and_stores_no_narration(desk, script):
    bia = desk.player("Bia")
    script.proposals.append(proposal(CHECK))
    joined = {}

    def caio_joins_meanwhile():  # muda a mesa (jogadores), não a revisão dos eventos
        script.before_reply = None
        joined["caio"] = desk.service.join_table(
            desk.id, JoinRequest(invite_code="convite", name="Caio")
        )

    script.before_reply = caio_joins_meanwhile
    error = desk.refused(bia, "tento")
    assert (error.status, error.code) == (409, "stale_revision")
    assert desk.service.get_table(desk.id, joined["caio"].token).revision >= 0  # a entrada ficou
    assert "check" not in [e.kind for e in desk.events(bia)]
    assert desk.service.storage.prose(desk.id) == {}


def test_a_stale_say_keeps_no_narration(desk, script):
    desk.cmd(desk.host, 'entrar ana "Ana"')
    bia = desk.player("Bia")
    script.proposals.append(proposal(CHECK))
    script.before_reply = lambda: desk.cmd(desk.host, "ferir bia 1")
    desk.refused(bia, "tento")
    assert desk.service.storage.prose(desk.id) == {}
    assert all(e.narration is None for e in desk.events(bia))


def test_a_second_say_while_one_is_running_is_refused(desk, script):
    desk.cmd(desk.host, 'entrar ana "Ana"')
    bia = desk.player("Bia")
    caio = desk.player("Caio")
    script.proposals.append(proposal(CHECK))
    inner = {}

    def caio_speaks_meanwhile():
        script.before_reply = None
        try:
            desk.say(caio, "eu também")
        except ApiFailure as exc:
            inner["error"] = exc

    script.before_reply = caio_speaks_meanwhile
    desk.say(bia, "tento")
    assert (inner["error"].status, inner["error"].code) == (409, "say_busy")


def test_the_slot_is_free_again_after_a_failure(desk, script):
    bia = desk.player("Bia")
    script.proposer_status = 500
    desk.refused(bia, "tento")
    script.proposer_status = 200
    script.proposals.append(proposal(CHECK))
    assert desk.say(bia, "tento de novo").commands == ["testar lutar normal"]


def test_two_simultaneous_says_apply_at_most_one(desk, script):
    desk.cmd(desk.host, 'entrar ana "Ana"')
    bia = desk.player("Bia")
    caio = desk.player("Caio")
    revisions = {t: desk.revision(t) for t in (bia, caio)}
    script.proposals += [proposal(CHECK), proposal(CHECK)]
    outcomes = []

    def speak(token):
        try:
            desk.say(token, "tento", revision=revisions[token])
            outcomes.append("ok")
        except ApiFailure as exc:
            outcomes.append(exc.code)

    threads = [threading.Thread(target=speak, args=(t,)) for t in (bia, caio)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert outcomes.count("ok") <= 1
    assert set(outcomes) <= {"ok", "say_busy", "stale_revision"}


# --- narração do LLM ---------------------------------------------------------------


def test_the_llm_paragraph_is_the_same_for_every_reader_and_only_in_memory(desk, script):
    desk.cmd(desk.host, 'entrar ana "Ana"')
    bia = desk.player("Bia")
    script.proposals.append(proposal(CHECK))
    result = desk.say(bia, "tento")
    assert result.events[0].narration == "O vento muda de direção."
    assert all(e.narration is None for e in result.events[1:])  # só o primeiro do lote
    assert all(e.prose and e.prose != "O vento muda de direção." for e in result.events)
    for token in (bia, desk.host):
        events = desk.events(token, result.events[0].index)
        assert events == result.events
    assert "O vento muda" not in desk.raw()  # a narração nunca vai ao arquivo


def test_if_the_narration_fails_the_grammar_is_used(desk, script, capsys):
    bia = desk.player("Bia")
    script.proposals.append(proposal(CHECK))
    script.narration_status = 500
    result = desk.say(bia, "tento")
    assert result.events[0].prose  # a da gramática continua lá
    assert result.events[0].narration is None
    assert "narração indisponível" in capsys.readouterr().err


def test_a_narration_in_data_format_is_dropped_and_the_grammar_is_used(desk, script):
    bia = desk.player("Bia")
    script.proposals.append(proposal(CHECK))
    script.narration = '{"x": 1}'
    result = desk.say(bia, "tento")
    assert result.events[0].narration is None
    assert result.events[0].prose
    assert desk.service.storage.prose(desk.id) == {}


def test_old_events_keep_the_grammar(desk, script):
    bia = desk.player("Bia")
    script.proposals.append(proposal(CHECK))
    desk.say(bia, "tento")
    first = desk.events(bia)[0]
    assert first.prose
    assert first.narration is None


def test_the_prose_paragraph_wakes_long_pollers_with_the_llm_text(desk, script):
    desk.cmd(desk.host, 'entrar ana "Ana"')
    bia = desk.player("Bia")
    seen = desk.revision(bia)
    script.proposals.append(proposal(CHECK))
    box = {}

    def poll():
        box["view"] = desk.service.get_events(desk.id, desk.host, seen, wait=10)

    thread = threading.Thread(target=poll)
    thread.start()
    desk.say(bia, "tento")
    thread.join(timeout=10)
    assert box["view"].events[0].narration == "O vento muda de direção."


def test_the_api_key_never_appears_in_a_say_result(desk, script):
    bia = desk.player("Bia")
    script.proposals.append(proposal(CHECK, say="ok"))
    result = desk.say(bia, "tento")
    assert "chave-secreta" not in result.model_dump_json()
    assert result.status is GameStatus.ACTIVE


# --- pela rota HTTP -----------------------------------------------------------------


def post(base, path, body, token):
    request = urllib.request.Request(  # noqa: S310 — servidor local do teste
        base + path,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310 — idem
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_say_over_http(desk, script):
    bia = desk.player("Bia")
    server = make_server("127.0.0.1", 0, desk.service)
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.02), daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        path = f"/tables/{desk.id}/say"
        revision = desk.revision(bia)
        script.proposals.append(proposal(CHECK, say="Boa sorte."))
        status, result = post(base, path, {"text": "tento", "revision": revision}, bia)
        assert status == 200
        assert result["say"] == "Boa sorte."
        assert result["commands"] == ["testar lutar normal"]
        assert result["events"][0]["narration"] == "O vento muda de direção."
        cases = [
            ({"text": "tento", "revision": revision}, bia, 409, "stale_revision"),
            ({"text": "tento"}, bia, 400, "bad_request"),
            ({"text": "", "revision": 0}, bia, 400, "bad_request"),
            ({"text": "a" + chr(0x202E) + "b", "revision": 0}, bia, 400, "bad_request"),
            ({"text": "x" * 501, "revision": 0}, bia, 400, "bad_request"),
            ({"text": "oi", "revision": 0}, "token-errado", 401, "unauthorized"),
        ]
        for body, token, expected_status, code in cases:
            got_status, got = post(base, path, body, token)
            assert (got_status, got["error"]["code"]) == (expected_status, code), body
    finally:
        server.shutdown()
        server.server_close()


# --- o que o LLM devolve chega limpo à tela dos outros -----------------------------


def test_control_and_invisible_characters_from_the_llm_never_reach_the_players(desk, script):
    bia = desk.player("Bia")
    dirty = "Bram diz:" + chr(0x1B) + "[2J ANA" + chr(0x202E) + " saiu" + chr(0x200B) + "."
    script.narration = dirty
    script.proposals.append(proposal(CHECK, say="Oi" + chr(0x1B) + "[31m" + chr(0x202E) + "!"))
    result = desk.say(bia, "tento")
    assert result.say == "Oi[31m!"
    assert result.events[0].narration == "Bram diz:[2J ANA saiu."


def test_only_the_latest_narrations_are_kept(desk):
    desk.service.storage.store_prose(desk.id, {i: f"p{i}" for i in range(MAX_NARRATIONS + 5)})
    kept = desk.service.storage.prose(desk.id)
    assert len(kept) == MAX_NARRATIONS
    assert min(kept) == 5
    assert kept[MAX_NARRATIONS + 4] == f"p{MAX_NARRATIONS + 4}"
