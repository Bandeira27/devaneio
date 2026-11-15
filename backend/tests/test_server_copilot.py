"""Copiloto do anfitrião: só ele pergunta e lê, o contexto é a campanha inteira e nada muda no jogo."""

import json
import threading
from itertools import count

import pytest
from pydantic import ValidationError

from conftest import CAMPAIGN_PATH
from devaneio.llm import LlmConfig
from devaneio.server import ApiFailure, Catalog, Storage, TableService
from devaneio.server.models import CommandRequest, CopilotRequest, CreateTableRequest, JoinRequest
from fakes import FakeLlmServer

TOKENS = count(1)
COPILOT_MARK = "copiloto do anfitrião"


class Script:
    def __init__(self):
        self.answer = "Sugestão: leve o grupo à floresta.\n\n- cuidado com o [segredo]."
        self.status = 200
        self.before_reply = None
        self.requests = []

    def respond(self, body):
        self.requests.append(body)
        system = body["messages"][0]["content"]
        if COPILOT_MARK in system:
            if self.before_reply:
                self.before_reply()
            if self.status != 200:
                return self.status, "falhou por dentro"
            return 200, self.answer
        return 200, '{"actions": [], "say": ""}'

    def copilot_calls(self):
        return [r for r in self.requests if COPILOT_MARK in r["messages"][0]["content"]]


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def script():
    return Script()


@pytest.fixture
def llm(script):
    with FakeLlmServer(script.respond) as server:
        yield server


@pytest.fixture
def clock():
    return Clock()


def make_service(tmp_path, llm, clock, *, cooldown=0, with_llm=True):
    config = LlmConfig(base_url=llm.base_url, model="m-teste", api_key="chave-secreta")
    return TableService(
        Catalog(CAMPAIGN_PATH.parent),
        Storage(tmp_path / "mesas", max_tables=4, clock=clock),
        llm=config if with_llm else None,
        say_cooldown=0,
        copilot_cooldown=cooldown,
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
        joined = service.join_table(self.id, JoinRequest(invite_code="convite", name="Bia"))
        self.player = joined.token

    def ask(self, token, text="e agora?"):
        return self.service.copilot(self.id, token, CopilotRequest(text=text))

    def refused(self, token, text="e agora?"):
        with pytest.raises(ApiFailure) as info:
            self.ask(token, text)
        return info.value

    def raw(self):
        return self.service.storage.path_for(self.id).read_text(encoding="utf-8")


@pytest.fixture
def desk(tmp_path, llm, clock):
    return Desk(make_service(tmp_path, llm, clock))


def test_the_host_gets_the_answer_as_plain_text(desk, script):
    answer = desk.ask(desk.host)
    assert answer.text == "Sugestão: leve o grupo à floresta.\n\n- cuidado com o [segredo]."
    (call,) = script.copilot_calls()
    assert "response_format" not in call  # texto livre, não JSON
    assert "PERGUNTA DO ANFITRIÃO\ne agora?" in call["messages"][1]["content"]


def test_the_prompt_has_the_whole_campaign_with_what_players_never_get(desk, script):
    desk.ask(desk.host)
    sent = script.copilot_calls()[0]["messages"][1]["content"]
    assert "Irmão Vael é o líder do culto." in sent  # fato oculto
    assert "Culto da Sombra" in sent  # facção
    assert '"estado":"pending"' in sent  # marco pendente
    assert '"kind":"npc_down"' in sent  # com as condições dele


def test_a_regular_player_cannot_consult_it_and_nothing_is_sent(desk, script):
    refused = desk.refused(desk.player)
    assert (refused.status, refused.code) == (403, "forbidden")
    assert script.requests == []


def test_auth_errors_come_before_anything_else(desk, script):
    assert desk.refused("token-errado").status == 401
    assert desk.refused(None).status == 401
    with pytest.raises(ApiFailure) as info:
        desk.service.copilot("0" * 16, desk.host, CopilotRequest(text="oi"))
    assert info.value.status == 404
    assert script.requests == []


def test_a_table_without_llm_refuses(tmp_path, llm, clock):
    desk = Desk(make_service(tmp_path, llm, clock, with_llm=False))
    refused = desk.refused(desk.host)
    assert (refused.status, refused.code) == (409, "llm_disabled")


def test_the_answer_never_reaches_the_table(desk, script):
    revision = desk.service.get_table(desk.id, desk.player).revision
    before = desk.raw()
    answer = desk.ask(desk.host)
    assert desk.raw() == before  # nada gravado
    assert answer.text not in desk.raw()
    for token in (desk.host, desk.player):
        view = desk.service.get_events(desk.id, token, 0)
        assert view.revision == revision
        assert view.talk == []  # o mural é de todos
        assert answer.text not in "".join(e.text + (e.narration or "") for e in view.events)


def test_the_question_is_not_recorded(desk):
    desk.ask(desk.host, "pergunta-que-nao-pode-ficar-registrada")
    assert "pergunta-que-nao-pode-ficar-registrada" not in desk.raw()


def test_the_answer_is_cleaned_for_the_hosts_screen(desk, script):
    script.answer = "oi\x1b[31m vermelho\u202e invertido\n\n\n\nfim"
    assert desk.ask(desk.host).text == "oi[31m vermelho invertido\n\nfim"


def test_an_llm_failure_is_a_generic_502_without_provider_detail(desk, script, capsys):
    script.status = 500
    refused = desk.refused(desk.host)
    assert (refused.status, refused.code) == (502, "llm_unavailable")
    assert "falhou por dentro" not in refused.message
    assert "chave-secreta" not in refused.message
    assert "llm:" in capsys.readouterr().err


def test_an_empty_answer_is_a_502_too(desk, script):
    script.answer = "\x1b \n"
    assert desk.refused(desk.host).status == 502


def test_only_one_consultation_at_a_time(desk, script):
    seen = []

    def interrupt():
        seen.append(desk.refused(desk.host))

    script.before_reply = interrupt
    assert desk.ask(desk.host).text
    (nested,) = seen
    assert (nested.status, nested.code) == (409, "copilot_busy")
    script.before_reply = None
    assert desk.ask(desk.host).text  # a vaga voltou


def test_the_copilot_seat_is_independent_from_the_free_text_seat(desk):
    storage = desk.service.storage
    assert storage.enter_say(desk.id)
    assert storage.enter_copilot(desk.id)
    assert not storage.enter_copilot(desk.id)
    storage.leave_copilot(desk.id)
    assert not storage.enter_say(desk.id)  # a do /say continua ocupada
    storage.leave_say(desk.id)


def test_the_interval_between_consultations_counts_even_on_failure(tmp_path, llm, clock, script):
    desk = Desk(make_service(tmp_path, llm, clock, cooldown=30))
    script.status = 500
    assert desk.refused(desk.host).status == 502
    limited = desk.refused(desk.host)
    assert (limited.status, limited.code) == (429, "copilot_rate_limited")
    assert "30 s" in limited.message
    clock.now += 29
    assert desk.refused(desk.host).status == 429
    clock.now += 2
    script.status = 200
    assert desk.ask(desk.host).text


def test_a_consultation_does_not_block_the_players_commands(desk, script):
    done = threading.Event()

    def during():
        revision = desk.service.get_table(desk.id, desk.player).revision
        desk.service.run_command(
            desk.id, desk.player, CommandRequest(line='entrar bia "Bia"', revision=revision)
        )
        done.set()

    script.before_reply = during
    desk.ask(desk.host)
    assert done.is_set()


def test_the_request_body_is_validated():
    with pytest.raises(ValidationError, match="text"):
        CopilotRequest(text="x" * 501)
    with pytest.raises(ValidationError, match="text"):
        CopilotRequest(text="a\x07b")
    assert json.loads(CopilotRequest(text="oi").model_dump_json()) == {"text": "oi"}
