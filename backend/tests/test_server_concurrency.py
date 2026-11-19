"""Concorrência com o banco: mesas diferentes ao mesmo tempo, a mesma mesa, o long-poll e a chamada lenta ao LLM."""

import threading
import time
from itertools import count

import pytest
from sqlalchemy import text

from conftest import CAMPAIGN_PATH, open_for_play
from devaneio.llm import LlmConfig
from devaneio.server import ApiFailure, Catalog, Storage, TableService
from devaneio.server.database import DB_NAME, Database
from devaneio.server.files import prepare_data_dir
from devaneio.server.migrations import migrate
from devaneio.server.models import CommandRequest, CreateTableRequest, SayRequest
from devaneio.server.storage import MAX_WAITERS
from fakes import FakeLlmServer

TOKENS = count(1)


def make_service(tmp_path, *, llm=None, **database_kwargs):
    database = Database(prepare_data_dir(tmp_path / "mesas") / DB_NAME, **database_kwargs)
    migrate(database)
    return TableService(
        Catalog(CAMPAIGN_PATH.parent),
        Storage(database, max_tables=20),
        llm=llm,
        say_cooldown=0,
        token_source=lambda: f"token-{next(TOKENS)}",
        invite_source=lambda: "convite",
    )


def new_table(service):
    created = service.create_table(
        CreateTableRequest(campaign_id="sombra-do-vale", host_name="Ana", seed=7)
    )
    open_for_play(service, created.table_id)
    return created


def end_turn(service, table_id, token):
    revision = service.get_table(table_id, token).revision
    return service.run_command(table_id, token, CommandRequest(line="fim", revision=revision))


def run_all(targets):
    errors = []
    barrier = threading.Barrier(len(targets))

    def wrap(target):
        try:
            barrier.wait()
            target()
        except Exception as exc:  # noqa: BLE001 — o teste junta tudo e falha com a lista
            errors.append(exc)

    threads = [threading.Thread(target=wrap, args=(target,)) for target in targets]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(60)
    return errors


def test_players_of_different_tables_act_at_the_same_time_without_locked_or_lost_events(tmp_path):
    service = make_service(tmp_path)
    tables = [new_table(service) for _ in range(6)]
    start = {t.table_id: len(service.load_session(t.table_id).state.events) for t in tables}
    rounds = 10

    def play(created):
        for _ in range(rounds):
            end_turn(service, created.table_id, created.host_token)

    assert run_all([lambda c=c: play(c) for c in tables]) == []
    gained = {
        t.table_id: len(service.load_session(t.table_id).state.events) - start[t.table_id]
        for t in tables
    }
    assert len(set(gained.values())) == 1  # todas as mesas andaram igual: nenhum evento se perdeu
    assert next(iter(gained.values())) >= rounds
    # o que o banco guardou é o que cada mesa vê
    for t in tables:
        view = service.get_table(t.table_id, t.host_token)
        assert view.revision == start[t.table_id] + gained[t.table_id]


def test_two_writers_with_the_same_revision_one_wins_and_the_other_is_stale(tmp_path):
    service = make_service(tmp_path)
    created = new_table(service)
    revision = service.get_table(created.table_id, created.host_token).revision
    results = []

    def race():
        try:
            service.run_command(
                created.table_id,
                created.host_token,
                CommandRequest(line="fim", revision=revision),  # os dois leram a mesma revisão
            )
            results.append("ok")
        except ApiFailure as exc:
            results.append(exc.code)

    assert run_all([race, race]) == []
    assert sorted(results) == ["ok", "stale_revision"]


def test_many_writers_on_the_same_table_lose_no_event(tmp_path):
    service = make_service(tmp_path)
    created = new_table(service)
    before = len(service.load_session(created.table_id).state.events)
    gained, refused = [], []

    def play():
        for _ in range(5):
            revision = service.get_table(created.table_id, created.host_token).revision
            try:
                result = service.run_command(
                    created.table_id,
                    created.host_token,
                    CommandRequest(line="fim", revision=revision),
                )
            except ApiFailure as exc:
                refused.append(exc.code)
            else:
                gained.append(len(result.events))

    assert run_all([play] * 6) == []
    assert gained  # alguém gravou
    assert set(refused) <= {"stale_revision"}  # só a revisão velha é recusada
    final = len(service.load_session(created.table_id).state.events)
    assert final == before + sum(gained)  # cada gravação aceita está lá, e nenhuma foi perdida


def test_sixteen_long_polls_hold_no_database_connection(tmp_path):
    service = make_service(tmp_path, pool_size=1, max_overflow=0, pool_timeout=15)
    created = new_table(service)
    token = created.host_token
    revision = service.get_table(created.table_id, token).revision
    answers, errors = [], []

    def wait_for_news():
        try:
            answers.append(service.get_events(created.table_id, token, revision, wait=10))
        except Exception as exc:  # noqa: BLE001 — o teste confere a lista no fim
            errors.append(exc)

    waiters = [threading.Thread(target=wait_for_news) for _ in range(MAX_WAITERS)]
    for waiter in waiters:
        waiter.start()
    deadline = time.monotonic() + 5
    while service.storage.waiting(created.table_id) < MAX_WAITERS and time.monotonic() < deadline:
        time.sleep(0.01)
    assert service.storage.waiting(created.table_id) == MAX_WAITERS
    # Com 16 esperando e uma só conexão no pool, ler e gravar seguem funcionando (cada um pega a conexão e a solta).
    assert service.get_table(created.table_id, token).revision == revision
    end_turn(service, created.table_id, token)
    for waiter in waiters:
        waiter.join(15)
    assert errors == []
    assert len(answers) == MAX_WAITERS
    assert all(answer.events for answer in answers)


@pytest.fixture
def slow_llm():
    entered, release = threading.Event(), threading.Event()
    seen = {}

    def respond(_body):
        entered.set()
        release.wait(10)
        return 200, '{"actions": [], "say": "Nada acontece."}'

    with FakeLlmServer(respond) as server:
        yield server, entered, release, seen


def test_no_transaction_is_open_while_the_llm_thinks(tmp_path, slow_llm):
    server, entered, release, _ = slow_llm
    config = LlmConfig(base_url=server.base_url, model="m", api_key="k")
    service = make_service(tmp_path, llm=config, busy_timeout_ms=200, retry_delays=())
    first, other = new_table(service), new_table(service)
    service.run_command(
        first.table_id,
        first.host_token,
        CommandRequest(
            line='entrar ana "Ana"',
            revision=service.get_table(first.table_id, first.host_token).revision,
        ),
    )
    revision = service.get_table(first.table_id, first.host_token).revision
    box = {}

    def talk():
        try:
            box["result"] = service.say(
                first.table_id,
                first.host_token,
                SayRequest(text="olho em volta", revision=revision),
            )
        except Exception as exc:  # noqa: BLE001 — conferido abaixo
            box["error"] = exc

    thread = threading.Thread(target=talk)
    thread.start()
    assert entered.wait(10), (
        box
    )  # o servidor de LLM está respondendo: a fase 2 do say está em curso
    begin = time.monotonic()
    # Um escritor qualquer não espera a fala: se houvesse transação de escrita aberta, o busy_timeout de 200 ms estouraria.
    service.storage._db.write(lambda s: s.execute(text("SELECT 1")))
    end_turn(service, other.table_id, other.host_token)  # outra mesa joga normalmente
    assert (
        service.get_table(first.table_id, first.host_token).revision == revision
    )  # e a mesma mesa lê
    assert time.monotonic() - begin < 3
    release.set()
    thread.join(15)
    assert "error" not in box, box.get("error")
    assert box["result"].say == "Nada acontece."
