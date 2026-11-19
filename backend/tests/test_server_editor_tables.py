"""As mesas de uma campanha no editor: listar, encerrar e reemitir o acesso do anfitrião (só da própria máquina)."""

import json
import threading
import time

import pytest

from conftest import CAMPAIGN_PATH
from devaneio.server import ApiFailure, Catalog, Storage, TableService
from devaneio.server.models import CreateTableRequest, InvitePreviewRequest
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
    storage = Storage(tmp_path / "mesas", max_tables=10)
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
    broken = storage.data_dir / "0123456789abcdef.json"
    broken.write_text("{isto não é json", encoding="utf-8")
    _, rows = api.call("GET", f"/editor/campaigns/{SOMBRA}/tables")
    assert [row["table_id"] for row in rows] == [good.table_id]


# --- encerrar -----------------------------------------------------------------------------


def test_closing_a_table_deletes_it_and_frees_the_campaign(api, setup):
    _, storage, service = setup
    created = make_table(service)
    assert writable(api) is False
    status, body = api.call("DELETE", f"/editor/tables/{created.table_id}", headers=origin(api))
    assert (status, body) == (200, {"table_id": created.table_id})
    assert storage.path_for(created.table_id) is None
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
    assert storage.path_for(created.table_id) is not None


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


def test_host_access_does_not_store_the_secrets_in_the_file(api, setup):
    _, storage, service = setup
    created = make_table(service)
    _, access = api.call(
        "POST", f"/editor/tables/{created.table_id}/host-access", headers=origin(api)
    )
    saved = storage.path_for(created.table_id).read_text(encoding="utf-8")
    assert access["token"] not in saved
    assert access["invite_code"] not in saved


def test_host_access_on_an_unknown_table_is_404(api):
    status, _ = api.call("POST", "/editor/tables/0123456789abcdef/host-access", headers=origin(api))
    assert status == 404


def test_host_access_on_an_unreadable_table_is_409(api, setup):
    _, storage, _ = setup
    (storage.data_dir / "0123456789abcdef.json").write_text("{quebrado", encoding="utf-8")
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
