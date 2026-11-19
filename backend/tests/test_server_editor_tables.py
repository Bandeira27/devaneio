"""As mesas de uma campanha no editor: listar, encerrar e reemitir o acesso do anfitrião (só da própria máquina)."""

import json
import threading
import time

import pytest

from conftest import CAMPAIGN_PATH, corrupt, make_storage, open_for_play, table_text
from devaneio.server import ApiFailure, Catalog, TableService
from devaneio.server.models import CommandRequest, CreateTableRequest, InvitePreviewRequest
from devaneio.server.storage import Record
from test_server_editor import SECRET, Api, serve

SOMBRA = "sombra-do-vale"


@pytest.fixture
def folder(tmp_path):
    root = tmp_path / "campanhas"
    root.mkdir()
    data = json.loads(CAMPAIGN_PATH.read_text(encoding="utf-8"))
    data["npcs"][0]["private_notes"] = [SECRET]
    (root / f"{SOMBRA}.json").write_text(json.dumps(data), encoding="utf-8")
    other = {**data, "id": "outra", "title": "Outra"}
    (root / "outra.json").write_text(json.dumps(other), encoding="utf-8")
    return root


@pytest.fixture
def setup(folder, tmp_path):
    catalog = Catalog(folder)
    storage = make_storage(tmp_path / "mesas", max_tables=10)
    return catalog, storage, TableService(catalog, storage)


@pytest.fixture
def api(setup):
    server = serve(setup)
    yield Api(server.server_address[1])
    server.shutdown()
    server.server_close()


def make_table(service, campaign_id=SOMBRA, host="Ana"):
    return service.create_table(CreateTableRequest(campaign_id=campaign_id, host_name=host, seed=1))


def writable(api):
    """Se a campanha principal está liberada para edição (a outra do teste nunca tem mesa)."""
    rows = api.call("GET", "/editor/campaigns")[1]
    return next(row["writable"] for row in rows if row["id"] == SOMBRA)


def origin(api):
    return {"Origin": f"http://localhost:{api.port}"}


# --- listar -----------------------------------------------------------------------------


def test_the_list_has_only_the_tables_of_that_campaign_and_no_secret(api, setup):
    _, _, service = setup
    mine = make_table(service)
    make_table(service, "outra", host="Beto")
    status, rows = api.call("GET", f"/editor/campaigns/{SOMBRA}/tables")
    assert status == 200
    assert [row["table_id"] for row in rows] == [mine.table_id]
    assert rows[0]["host_name"] == "Ana"
    assert rows[0]["players"] == 1
    assert rows[0]["phase"] == "lobby"
    text = json.dumps(rows)
    for secret in (mine.host_token, mine.invite_code, "hash", "token", SECRET):
        assert secret not in text


def test_an_unknown_campaign_is_404_and_a_campaign_without_tables_is_empty(api):
    assert api.call("GET", "/editor/campaigns/nao-existe/tables")[0] == 404
    assert api.call("GET", f"/editor/campaigns/{SOMBRA}/tables") == (200, [])


def test_an_unreadable_table_does_not_break_the_list(api, setup):
    _, storage, service = setup
    good = make_table(service)
    storage.create(
        "0123456789abcdef",
        Record(campaign_path=f"{SOMBRA}.json", state="{}", meta="{isto não é json", content=None),
    )
    _, rows = api.call("GET", f"/editor/campaigns/{SOMBRA}/tables")
    assert [row["table_id"] for row in rows] == [good.table_id]


# --- encerrar -----------------------------------------------------------------------------


def test_closing_a_table_archives_it_and_frees_the_campaign(api, setup):
    _, storage, service = setup
    created = make_table(service)
    assert writable(api) is False
    status, body = api.call("DELETE", f"/editor/tables/{created.table_id}", headers=origin(api))
    assert (status, body) == (200, {"table_id": created.table_id})
    assert not storage.exists(created.table_id)
    assert writable(api) is True
    assert api.call("GET", f"/editor/campaigns/{SOMBRA}/tables") == (200, [])


def test_closing_an_unknown_or_malformed_table_is_404(api):
    for table_id in ("0123456789abcdef", "..%2F..%2Fx", "ABC"):
        status, _ = api.call("DELETE", f"/editor/tables/{table_id}", headers=origin(api))
        assert status == 404


def test_closing_needs_a_same_origin_request(api, setup):
    _, storage, service = setup
    created = make_table(service)
    status, body = api.call(
        "DELETE",
        f"/editor/tables/{created.table_id}",
        headers={"Origin": "http://exemplo.com"},
    )
    assert status == 403
    assert body["error"]["code"] == "origin_not_allowed"
    assert storage.exists(created.table_id)


def test_closing_wakes_a_waiting_reader_with_404(api, setup):
    _, _, service = setup
    created = make_table(service)
    seen = service.get_table(created.table_id, created.host_token).revision
    box = {}

    def read():
        started = time.monotonic()
        try:
            service.get_events(created.table_id, created.host_token, seen, wait=10)
        except ApiFailure as exc:
            box["status"] = exc.status
        box["elapsed"] = time.monotonic() - started

    thread = threading.Thread(target=read)
    thread.start()
    time.sleep(0.3)
    api.call("DELETE", f"/editor/tables/{created.table_id}", headers=origin(api))
    thread.join(timeout=10)
    assert box["status"] == 404
    assert box["elapsed"] < 5  # acordou pelo encerramento, não pelo prazo


# --- arquivar, restaurar, apagar de vez e o histórico ----------------------------------------


def archive(api, created):
    return api.call("DELETE", f"/editor/tables/{created.table_id}", headers=origin(api))


def test_archiving_keeps_the_state_and_moves_the_table_to_the_archived_list(api, setup):
    _, storage, service = setup
    created = make_table(service)
    status, body = archive(api, created)
    assert (status, body) == (200, {"table_id": created.table_id})
    assert storage.exists(created.table_id) is False  # fora do jogo
    assert storage.exists(created.table_id, scope="archived") is True  # mas guardada
    assert api.call("GET", f"/editor/campaigns/{SOMBRA}/tables") == (200, [])
    status, rows = api.call("GET", f"/editor/campaigns/{SOMBRA}/archived-tables")
    assert status == 200
    [row] = rows
    assert (row["table_id"], row["host_name"], row["players"]) == (created.table_id, "Ana", 1)
    assert row["archived_at"] >= row["updated_at"] > 0
    for secret in (created.host_token, created.invite_code, "hash", "token"):
        assert secret not in json.dumps(rows)


def test_an_archived_table_is_gone_for_the_players_and_does_not_hold_the_campaign(api, setup):
    _, _, service = setup
    created = make_table(service)
    assert writable(api) is False
    archive(api, created)
    assert writable(api) is True  # só mesa ativa trava a campanha
    for call in (
        lambda: service.get_table(created.table_id, created.host_token),
        lambda: service.get_events(created.table_id, created.host_token, 0),
        lambda: service.preview_invite(
            created.table_id, InvitePreviewRequest(invite_code=created.invite_code)
        ),
    ):
        with pytest.raises(ApiFailure) as info:
            call()
        assert info.value.status in (401, 404)


def test_archiving_twice_or_an_unknown_table_is_404(api, setup):
    _, _, service = setup
    created = make_table(service)
    assert archive(api, created)[0] == 200
    assert archive(api, created)[0] == 404
    status, _ = api.call("DELETE", "/editor/tables/0123456789abcdef", headers=origin(api))
    assert status == 404


def test_restoring_brings_the_same_table_back_with_the_old_token_and_invite(api, setup):
    _, _, service = setup
    created = make_table(service)
    before = service.get_table(created.table_id, created.host_token).revision
    archive(api, created)
    status, row = api.call(
        "POST", f"/editor/archived-tables/{created.table_id}/restore", headers=origin(api)
    )
    assert status == 200
    assert (row["table_id"], row["host_name"], row["phase"]) == (created.table_id, "Ana", "lobby")
    assert service.get_table(created.table_id, created.host_token).revision == before
    assert service.preview_invite(
        created.table_id, InvitePreviewRequest(invite_code=created.invite_code)
    ).title
    assert api.call("GET", f"/editor/campaigns/{SOMBRA}/archived-tables") == (200, [])
    assert writable(api) is False  # voltou a travar a campanha


def test_restoring_an_active_or_unknown_table_is_404(api, setup):
    _, _, service = setup
    created = make_table(service)
    for table_id in (created.table_id, "0123456789abcdef"):
        status, _ = api.call(
            "POST", f"/editor/archived-tables/{table_id}/restore", headers=origin(api)
        )
        assert status == 404


def test_restoring_respects_the_table_limit(tmp_path, folder):
    catalog = Catalog(folder)
    storage = make_storage(tmp_path / "mesas", max_tables=1)
    service = TableService(catalog, storage)
    server = serve((catalog, storage, service))
    api = Api(server.server_address[1])
    try:
        first = make_table(service)
        archive(api, first)
        make_table(service)  # a vaga do arquivamento foi usada por outra mesa
        status, body = api.call(
            "POST", f"/editor/archived-tables/{first.table_id}/restore", headers=origin(api)
        )
        assert (status, body["error"]["code"]) == (409, "table_limit")
        assert storage.exists(first.table_id, scope="archived")  # segue arquivada
    finally:
        server.shutdown()
        server.server_close()


def test_a_table_whose_game_no_longer_fits_the_campaign_stays_archived_with_its_date(api, setup):
    _, storage, service = setup
    created = make_table(service)
    archive(api, created)
    [before] = storage.summaries("sombra-do-vale.json", scope="archived")
    corrupt(service, created.table_id, state='{"state": "estragado"}')
    status, body = api.call(
        "POST", f"/editor/archived-tables/{created.table_id}/restore", headers=origin(api)
    )
    assert (status, body["error"]["code"]) == (409, "table_unreadable")
    assert "não combina mais com a campanha" in body["error"]["message"]
    assert storage.exists(created.table_id) is False
    assert storage.exists(created.table_id, scope="archived") is True
    [after] = storage.summaries("sombra-do-vale.json", scope="archived")
    assert after.archived_at == before.archived_at  # a data original do arquivamento não mudou


@pytest.mark.parametrize("table_id", ["inventado", "0123456789abcdef", "ABC", "x" * 64])
def test_an_invented_id_creates_no_lock_entry_in_memory(api, setup, table_id):
    _, storage, _ = setup
    before = len(storage._tables)
    for method, path in (
        ("POST", f"/editor/archived-tables/{table_id}/restore"),
        ("DELETE", f"/editor/archived-tables/{table_id}"),
    ):
        assert api.call(method, path, headers=origin(api))[0] == 404
    assert len(storage._tables) == before


def test_purging_deletes_only_an_archived_table_and_for_good(api, setup):
    _, storage, service = setup
    created = make_table(service)
    status, _ = api.call(
        "DELETE", f"/editor/archived-tables/{created.table_id}", headers=origin(api)
    )
    assert status == 404  # ativa: só arquivar a tira do jogo
    assert storage.exists(created.table_id)
    archive(api, created)
    status, body = api.call(
        "DELETE", f"/editor/archived-tables/{created.table_id}", headers=origin(api)
    )
    assert (status, body) == (200, {"table_id": created.table_id})
    assert storage.exists(created.table_id, scope="any") is False
    assert api.call("GET", f"/editor/campaigns/{SOMBRA}/archived-tables") == (200, [])


def test_the_history_of_an_archived_table_is_its_whole_log_and_nothing_secret(api, setup):
    _, _, service = setup
    created = make_table(service)
    open_for_play(service, created.table_id)
    view = service.get_table(created.table_id, created.host_token)
    service.run_command(
        created.table_id,
        created.host_token,
        CommandRequest(line='entrar ana "Ana"', revision=view.revision),
    )
    expected = service.load_session(created.table_id).state.events
    assert expected
    archive(api, created)
    status, log = api.call("GET", f"/editor/archived-tables/{created.table_id}/log")
    assert status == 200
    assert [(e["index"], e["turn"], e["kind"], e["text"]) for e in log["events"]] == [
        (i, e.turn, e.kind, e.text) for i, e in enumerate(expected)
    ]
    text = json.dumps(log)
    for secret in (created.host_token, created.invite_code, "token_hash", "invite_hash", SECRET):
        assert secret not in text


def test_the_history_only_exists_for_archived_tables(api, setup):
    _, _, service = setup
    created = make_table(service)
    assert api.call("GET", f"/editor/archived-tables/{created.table_id}/log")[0] == 404
    assert api.call("GET", "/editor/archived-tables/0123456789abcdef/log")[0] == 404


def test_the_archive_routes_need_a_same_origin_request_and_the_editor(api, setup, folder):
    _, _, service = setup
    created = make_table(service)
    archive(api, created)
    bad = {"Origin": "http://exemplo.com"}
    for method, path in (
        ("POST", f"/editor/archived-tables/{created.table_id}/restore"),
        ("DELETE", f"/editor/archived-tables/{created.table_id}"),
    ):
        status, body = api.call(method, path, headers=bad)
        assert (status, body["error"]["code"]) == (403, "origin_not_allowed")
    server = serve(setup, editor=False)
    off = Api(server.server_address[1])
    for path in (
        f"/editor/campaigns/{SOMBRA}/archived-tables",
        f"/editor/archived-tables/{created.table_id}/log",
    ):
        assert off.call("GET", path)[0] == 404
    server.shutdown()
    server.server_close()


# --- reemitir o acesso do anfitrião -----------------------------------------------------------


def test_host_access_replaces_the_token_and_the_invite(api, setup):
    _, _, service = setup
    created = make_table(service)
    status, access = api.call(
        "POST", f"/editor/tables/{created.table_id}/host-access", headers=origin(api)
    )
    assert status == 200
    assert access["table_id"] == created.table_id
    assert access["player_id"] == "p1"
    assert access["token"] != created.host_token
    assert access["invite_code"] != created.invite_code
    with pytest.raises(ApiFailure) as old:
        service.get_table(created.table_id, created.host_token)
    assert old.value.status == 401
    assert service.get_table(created.table_id, access["token"]).you == "p1"
    with pytest.raises(ApiFailure):
        service.preview_invite(
            created.table_id, InvitePreviewRequest(invite_code=created.invite_code)
        )
    new_invite = InvitePreviewRequest(invite_code=access["invite_code"])
    assert service.preview_invite(created.table_id, new_invite).title


def test_host_access_does_not_store_the_secrets_in_the_database(api, setup):
    _, _, service = setup
    created = make_table(service)
    _, access = api.call(
        "POST", f"/editor/tables/{created.table_id}/host-access", headers=origin(api)
    )
    saved = table_text(service, created.table_id)
    assert access["token"] not in saved
    assert access["invite_code"] not in saved


def test_host_access_on_an_unknown_table_is_404(api):
    status, _ = api.call("POST", "/editor/tables/0123456789abcdef/host-access", headers=origin(api))
    assert status == 404


def test_host_access_on_an_unreadable_table_is_409(api, setup):
    _, storage, _ = setup
    storage.create(
        "0123456789abcdef",
        Record(campaign_path=f"{SOMBRA}.json", state="{quebrado", meta="{quebrado", content=None),
    )
    status, body = api.call(
        "POST", "/editor/tables/0123456789abcdef/host-access", headers=origin(api)
    )
    assert status == 409
    assert body["error"]["code"] == "table_unreadable"


def test_the_table_routes_do_not_exist_without_the_editor(setup):
    server = serve(setup, editor=False)
    api = Api(server.server_address[1])
    try:
        for method, path in (
            ("GET", f"/editor/campaigns/{SOMBRA}/tables"),
            ("DELETE", "/editor/tables/0123456789abcdef"),
            ("POST", "/editor/tables/0123456789abcdef/host-access"),
        ):
            assert api.call(method, path, headers=origin(api))[0] == 404
    finally:
        server.shutdown()
        server.server_close()
