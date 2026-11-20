"""Servidor HTTP em processo (porta 0) e cliente urllib: rotas, limites e erros."""

import http.client
import json
import re
import threading
import urllib.error
import urllib.request
from itertools import count

import pytest

from conftest import CAMPAIGN_PATH, corrupt, make_storage, open_for_play
from devaneio.game import new_game, save_game
from devaneio.llm import LlmConfig
from devaneio.server import ApiFailure, Catalog, TableService
from devaneio.server.__main__ import main
from devaneio.server.http import ApiServer, make_server
from fakes import FakeLlmServer

TOKENS = count(1)


class Client:
    def __init__(self, base_url, service=None):
        self.base_url = base_url
        self.service = service  # para abrir a partida das mesas criadas (``create``)

    def call(self, method, path, *, body=None, auth=None, headers=None, raw=None):
        data = None
        hdrs = dict(headers or {})
        if body is not None or raw is not None:
            data = raw if raw is not None else json.dumps(body).encode("utf-8")
            hdrs.setdefault("Content-Type", "application/json")
        if auth:
            hdrs["Authorization"] = f"Bearer {auth}"
        request = urllib.request.Request(  # noqa: S310 — URL local do teste
            self.base_url + path, data=data, headers=hdrs, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310 — URL local do teste
                return response.status, json.loads(response.read()), dict(response.headers)
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read()), dict(exc.headers)

    def connection(self):
        """Conexão crua, para requisições que o urllib não monta (cabeçalhos a mão)."""
        host, port = self.base_url.removeprefix("http://").split(":")
        return http.client.HTTPConnection(host, int(port), timeout=5)


@pytest.fixture
def issued():
    """Tokens que o serviço entregou, na ordem: o que a API devolve tem de vir daqui."""
    return []


@pytest.fixture
def service(tmp_path, issued):
    def issue():
        issued.append(f"token-{next(TOKENS)}")
        return issued[-1]

    return TableService(
        Catalog(CAMPAIGN_PATH.parent),
        make_storage(tmp_path / "mesas", max_tables=5),
        token_source=issue,
        invite_source=lambda: "convite",
    )


@pytest.fixture
def client(service):
    server = make_server("127.0.0.1", 0, service)
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.02), daemon=True)
    thread.start()
    try:
        yield Client(f"http://127.0.0.1:{server.server_address[1]}", service)
    finally:
        server.shutdown()
        server.server_close()


def create(client, *, lobby=False, **fields):
    """Cria a mesa; sem ``lobby`` ela já vem em andamento (como antes da sala de espera)."""
    body = {"campaign_id": "sombra-do-vale", "host_name": "Ana", "seed": 7, **fields}
    status, created, headers = client.call("POST", "/tables", body=body)
    if status == 201 and not lobby:
        open_for_play(client.service, created["table_id"])
    return status, created, headers


def test_create_then_read_a_table(client, issued):
    status, listed, _ = client.call("GET", "/campaigns")
    assert status == 200
    assert listed == [
        {
            "id": "sombra-do-vale",
            "title": "A Sombra do Vale",
            "premise": listed[0]["premise"],
        }
    ]

    status, created, headers = create(client, lobby=True)
    assert status == 201
    assert headers["Content-Type"] == "application/json; charset=utf-8"
    assert headers["Cache-Control"] == "no-store"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Server"].strip() == "devaneio"
    assert created["host_token"] == issued[-1]
    assert created["invite_code"] == "convite"
    assert "hash" not in json.dumps(created)
    table_id = created["table_id"]
    token = created["host_token"]

    status, view, _ = client.call("GET", f"/tables/{table_id}", auth=token)
    assert status == 200
    assert view == created["table"]
    assert view["state"]["rng_seed"] == 7
    assert (view["phase"], view["elapsed_seconds"], view["revision"]) == ("lobby", 0, 0)
    assert view["players"] == [{"id": "p1", "name": "Ana", "role": "host", "character_ids": []}]
    assert "hash" not in json.dumps(view)

    status, campaign, _ = client.call("GET", f"/tables/{table_id}/campaign", auth=token)
    assert status == 200
    assert campaign["id"] == "sombra-do-vale"


def test_a_player_joins_with_the_invite_and_sees_the_projected_state(client, issued):
    _, created, _ = create(client)
    table_id = created["table_id"]
    status, joined, _ = client.call(
        "POST", f"/tables/{table_id}/players", body={"invite_code": "convite", "name": "Bia"}
    )
    assert status == 201
    assert joined["player_id"] == "p2"
    assert joined["token"] == issued[-1]
    assert "rng_seed" not in joined["table"]["state"]

    status, view, _ = client.call("GET", f"/tables/{table_id}", auth=joined["token"])
    assert status == 200
    assert view == joined["table"]
    assert "hash" not in json.dumps(view)
    status, host_view, _ = client.call("GET", f"/tables/{table_id}", auth=created["host_token"])
    assert host_view["state"]["rng_seed"] == 7
    assert [p["name"] for p in host_view["players"]] == ["Ana", "Bia"]


def test_a_player_reads_the_campaign_as_olhar_shows_it(client):
    _, created, _ = create(client)
    table_id = created["table_id"]
    _, joined, _ = client.call(
        "POST", f"/tables/{table_id}/players", body={"invite_code": "convite", "name": "Bia"}
    )
    status, view, _ = client.call("GET", f"/tables/{table_id}/campaign", auth=joined["token"])
    assert status == 200
    assert view["location"]["id"] == "vila"
    assert [n["id"] for n in view["npcs"]] == ["ferreiro"]
    assert "factions" not in view
    status, whole, _ = client.call(
        "GET", f"/tables/{table_id}/campaign", auth=created["host_token"]
    )
    assert status == 200
    assert whole["factions"][0]["goals"]


def play_setup(client):
    """Mesa com Ana (anfitriã) e Bia (jogadora, com o personagem `bia`)."""
    _, created, _ = create(client)
    table_id = created["table_id"]
    _, joined, _ = client.call(
        "POST", f"/tables/{table_id}/players", body={"invite_code": "convite", "name": "Bia"}
    )
    path = f"/tables/{table_id}/commands"
    status, result, _ = client.call(
        "POST", path, body={"line": 'entrar bia "Bia"', "revision": 1}, auth=joined["token"]
    )
    assert status == 200
    return table_id, path, created["host_token"], joined["token"], result


def test_a_player_enters_acts_and_reads_the_events_over_http(client):
    table_id, path, host, bia, entered = play_setup(client)
    assert entered["revision"] == 2
    assert [e["kind"] for e in entered["events"]] == ["character_joined"]
    assert "data" not in entered["events"][0]

    status, result, _ = client.call(
        "POST", path, body={"line": "testar lutar normal", "revision": 2}, auth=bia
    )
    assert status == 200
    assert result["turn_ended"] is True  # Bia é a única com personagem: o turno fecha
    assert result["status"] == "active"

    status, events, _ = client.call("GET", f"/tables/{table_id}/events?since=2", auth=bia)
    assert status == 200
    assert events["revision"] == result["revision"]
    assert [e["index"] for e in events["events"]] == list(range(2, events["revision"]))
    assert events["events"][0]["kind"] == "check"
    assert events["events"][0]["prose"]
    status, everything, _ = client.call("GET", f"/tables/{table_id}/events", auth=host)
    assert everything["events"][2:] == events["events"]


def test_command_errors_over_http(client):
    _table_id, path, host, bia, _ = play_setup(client)
    cases = [
        (bia, {"line": "fim", "revision": 2}, 403, "forbidden"),
        (bia, {"line": "testar lutar normal", "revision": 1}, 409, "stale_revision"),
        (bia, {"line": "testar lutar impossivel", "revision": 2}, 422, "command_refused"),
        (bia, {"line": "dançar", "revision": 2}, 422, "command_refused"),
        (bia, {"line": "ana: testar lutar normal", "revision": 2}, 403, "forbidden"),
        (bia, {"line": "", "revision": 2}, 400, "bad_request"),
        (bia, {"line": "   ", "revision": 2}, 400, "bad_request"),
        (bia, {"line": 'entrar x "A\u202eB"', "revision": 2}, 400, "bad_request"),
        (bia, {"line": "olhar\nfim", "revision": 2}, 400, "bad_request"),
        (bia, {"line": "olhar"}, 400, "bad_request"),
        (bia, {"line": "olhar", "revision": -1}, 400, "bad_request"),
        (bia, {"line": "x" * 501, "revision": 2}, 400, "bad_request"),
        (None, {"line": "olhar", "revision": 2}, 401, "unauthorized"),
        ("token-errado", {"line": "olhar", "revision": 2}, 401, "unauthorized"),
    ]
    for token, body, status, code in cases:
        got_status, got, _ = client.call("POST", path, body=body, auth=token)
        assert (got_status, got["error"]["code"]) == (status, code), body
    status, _, _ = client.call(
        "POST",
        "/tables/0123456789abcdef/commands",
        body={"line": "olhar", "revision": 0},
        auth=host,
    )
    assert status == 404


@pytest.mark.parametrize(
    ("headers", "raw", "status", "code"),
    [
        (
            {"Content-Type": "text/plain"},
            b'{"line":"olhar","revision":2}',
            415,
            "unsupported_media_type",
        ),
        ({"Content-Type": "application/json"}, b"", 400, "bad_request"),
        ({"Content-Type": "application/json"}, b"[]", 400, "bad_request"),
        (
            {"Content-Type": "application/json"},
            b'{"line":"olhar","revision":2,"x":1}',
            400,
            "bad_request",
        ),
    ],
    ids=["content-type", "sem-corpo", "nao-objeto", "campo-extra"],
)
def test_the_commands_route_validates_the_body_before_anything_else(
    client, headers, raw, status, code
):
    _table_id, path, _host, bia, _ = play_setup(client)
    got_status, body, _ = client.call("POST", path, raw=raw, headers=headers, auth=bia)
    assert (got_status, body["error"]["code"]) == (status, code)


def test_the_commands_route_without_content_length_is_411(client):
    _table_id, path, _host, bia, _ = play_setup(client)
    conn = client.connection()
    conn.putrequest("POST", path)
    conn.putheader("Content-Type", "application/json")
    conn.putheader("Authorization", f"Bearer {bia}")
    conn.endheaders()
    response = conn.getresponse()
    body = json.loads(response.read())
    conn.close()
    assert (response.status, body["error"]["code"]) == (411, "length_required")


def test_the_events_of_a_table_do_not_open_to_a_token_of_another(client):
    table_id, _, _host, _bia, _ = play_setup(client)
    _, other, _ = create(client)
    status, body, _ = client.call("GET", f"/tables/{table_id}/events", auth=other["host_token"])
    assert (status, body["error"]["code"]) == (401, "unauthorized")


def test_events_query_and_auth_errors(client):
    table_id, _, _host, bia, _ = play_setup(client)
    for query in ("since=-1", "since=x", "since=1&since=2", "since=" + "9" * 12, "since=%C2%B2"):
        status, body, _ = client.call("GET", f"/tables/{table_id}/events?{query}", auth=bia)
        assert (status, body["error"]["code"]) == (400, "bad_request"), query
    status, body, _ = client.call("GET", f"/tables/{table_id}/events")
    assert (status, body["error"]["code"]) == (401, "unauthorized")
    status, events, _ = client.call("GET", f"/tables/{table_id}/events?since=999", auth=bia)
    assert status == 200
    assert events["events"] == []
    status, events, _ = client.call("GET", f"/tables/{table_id}/events?outro=1", auth=bia)
    assert status == 200  # parâmetro desconhecido é ignorado


def test_long_poll_over_http_wakes_on_a_command(client):
    table_id, path, _host, bia, entered = play_setup(client)
    seen = entered["revision"]
    box = {}

    def poll():
        box["answer"] = client.call(
            "GET", f"/tables/{table_id}/events?since={seen}&wait=10", auth=bia
        )

    thread = threading.Thread(target=poll)
    thread.start()
    status, _, _ = client.call(
        "POST", path, body={"line": "testar lutar normal", "revision": seen}, auth=bia
    )
    assert status == 200
    thread.join(timeout=10)
    status, events, _ = box["answer"]
    assert status == 200
    assert events["events"][0]["kind"] == "check"


@pytest.mark.parametrize("wait", ["31", "-1", "x", "1.5", "1&wait=2"])
def test_wait_must_be_an_integer_up_to_thirty(client, wait):
    table_id, _, _, bia, _ = play_setup(client)
    status, body, _ = client.call("GET", f"/tables/{table_id}/events?wait={wait}", auth=bia)
    assert (status, body["error"]["code"]) == (400, "bad_request")


def test_wait_thirty_is_accepted(client):
    table_id, _, _, bia, _ = play_setup(client)
    status, events, _ = client.call("GET", f"/tables/{table_id}/events?since=0&wait=30", auth=bia)
    assert status == 200  # há eventos desde 0: volta na hora
    assert events["events"]


def test_a_refused_command_leaves_the_table_as_it_was(client):
    table_id, path, host, bia, _ = play_setup(client)
    _, before, _ = client.call("GET", f"/tables/{table_id}", auth=host)
    client.call("POST", path, body={"line": "fim", "revision": 2}, auth=bia)
    client.call("POST", path, body={"line": "testar lutar impossivel", "revision": 2}, auth=bia)
    _, after, _ = client.call("GET", f"/tables/{table_id}", auth=host)
    assert after == before


def test_invite_preview_answers_with_the_title_and_nothing_else(client):
    _, created, _ = create(client)
    path = f"/tables/{created['table_id']}/preview"
    status, body, _ = client.call("POST", path, body={"invite_code": "convite"})  # sem token
    assert (status, body) == (200, {"title": "A Sombra do Vale"})


def test_invite_preview_errors_do_not_say_whether_the_table_exists(client):
    _, created, _ = create(client)
    wrong = client.call(
        "POST", f"/tables/{created['table_id']}/preview", body={"invite_code": "errado"}
    )
    unknown = client.call(
        "POST", "/tables/0123456789abcdef/preview", body={"invite_code": "convite"}
    )
    assert wrong[0] == unknown[0] == 401
    assert wrong[1] == unknown[1]  # mesmo código e mesma mensagem
    assert wrong[1]["error"]["code"] == "invalid_invite"


def test_invite_preview_needs_a_json_content_type(client):
    _, created, _ = create(client)
    status, body, _ = client.call(
        "POST",
        f"/tables/{created['table_id']}/preview",
        raw=b'{"invite_code": "convite"}',
        headers={"Content-Type": "text/plain"},
    )
    assert (status, body["error"]["code"]) == (415, "unsupported_media_type")


@pytest.mark.parametrize("body", [{}, {"invite_code": "x" * 65}])
def test_invite_preview_rejects_an_invalid_body(client, body):
    _, created, _ = create(client)
    status, got, _ = client.call("POST", f"/tables/{created['table_id']}/preview", body=body)
    assert (status, got["error"]["code"]) == (400, "bad_request")


def test_invite_preview_rejects_empty_extra_and_long_codes_but_takes_sixty_four(client):
    _, created, _ = create(client)
    path = f"/tables/{created['table_id']}/preview"
    for bad in ({"invite_code": ""}, {"invite_code": "convite", "name": "Bia"}):
        status, body, _ = client.call("POST", path, body=bad)
        assert (status, body["error"]["code"]) == (400, "bad_request")
    status, body, _ = client.call("POST", path, body={"invite_code": "x" * 64})
    assert (status, body["error"]["code"]) == (401, "invalid_invite")  # passou da validação


def test_invite_preview_refuses_get_with_405(client):
    _, created, _ = create(client)
    status, body, _ = client.call("GET", f"/tables/{created['table_id']}/preview")
    assert (status, body["error"]["code"]) == (405, "method_not_allowed")


def test_invite_preview_of_a_loose_save_file_is_401(client, tmp_path):
    table_id = "0123456789abcdef"
    save_game(new_game(CAMPAIGN_PATH, tmp_path / "mesas" / f"{table_id}.json", seed=7))
    status, body, _ = client.call(
        "POST", f"/tables/{table_id}/preview", body={"invite_code": "convite"}
    )
    assert (status, body["error"]["code"]) == (401, "invalid_invite")


def test_join_errors(client):
    _, created, _ = create(client)
    path = f"/tables/{created['table_id']}/players"
    cases = [
        (path, {"invite_code": "errado", "name": "Bia"}, 401, "invalid_invite"),
        (
            "/tables/0123456789abcdef/players",
            {"invite_code": "convite", "name": "Bia"},
            401,
            "invalid_invite",
        ),
        (path, {"invite_code": "convite"}, 400, "bad_request"),
        (path, {"invite_code": "convite", "name": "x" * 41}, 400, "bad_request"),
        (path, {"invite_code": "convite", "name": "Ana\u200b"}, 400, "bad_request"),
    ]
    for case_path, body, status, code in cases:
        got_status, got, _ = client.call("POST", case_path, body=body)
        assert (got_status, got["error"]["code"]) == (status, code), body
    client.call("POST", path, body={"invite_code": "convite", "name": "Bia"})
    status, body, _ = client.call("POST", path, body={"invite_code": "convite", "name": "Bia"})
    assert (status, body["error"]["code"]) == (409, "name_taken")


def test_errors_are_json_with_code_and_message(client):
    _, created, _ = create(client)
    table_id = created["table_id"]
    cases = [
        (("GET", "/nada"), 404, "not_found"),
        (("GET", "/tables"), 405, "method_not_allowed"),
        (("GET", f"/tables/{table_id}"), 401, "unauthorized"),
        (("GET", "/tables/..%2F..%2Fetc%2Fpasswd"), 404, "table_not_found"),
        (("GET", "/tables/0123456789abcdef"), 404, "table_not_found"),
        (("POST", "/tables", {"campaign_id": "nada", "host_name": "x"}), 404, "campaign_not_found"),
        (("POST", "/tables", {"campaign_id": "sombra-do-vale"}), 400, "bad_request"),
        (
            ("POST", "/tables", {"campaign_id": "sombra-do-vale", "host_name": "x", "extra": 1}),
            400,
            "bad_request",
        ),
    ]
    for args, status, code in cases:
        method, path, *rest = args
        got_status, body, _ = client.call(method, path, body=rest[0] if rest else None)
        assert (got_status, body["error"]["code"]) == (status, code), args
        assert set(body["error"]) == {"code", "message"}


@pytest.mark.parametrize(
    ("headers", "raw", "status", "code"),
    [
        ({"Content-Type": "text/plain"}, b"{}", 415, "unsupported_media_type"),
        ({"Content-Type": "application/json"}, b"{not json", 400, "bad_request"),
        # recusado sem ler o corpo: sem corpo no teste, para o cliente não levar reset ao escrever
        (
            {"Content-Type": "application/json", "Transfer-Encoding": "chunked"},
            None,
            400,
            "bad_request",
        ),
    ],
    ids=["content-type", "json-invalido", "transfer-encoding"],
)
def test_body_limits_and_content_type(client, headers, raw, status, code):
    got_status, body, _ = client.call("POST", "/tables", raw=raw, headers=headers)
    assert (got_status, body["error"]["code"]) == (status, code)


def test_missing_content_length_is_411(client):
    conn = client.connection()
    conn.putrequest("POST", "/tables", skip_accept_encoding=True)
    conn.putheader("Content-Type", "application/json")
    conn.endheaders()
    response = conn.getresponse()
    body = json.loads(response.read())
    conn.close()
    assert (response.status, body["error"]["code"]) == (411, "length_required")


def test_oversized_declared_body_is_refused_before_being_read(client):
    """Content-Length acima do limite com só 10 bytes no fio: a resposta chega dentro do
    timeout do cliente (5 s), logo o servidor não ficou esperando os 100000 bytes."""
    conn = client.connection()
    conn.putrequest("POST", "/tables")
    conn.putheader("Content-Type", "application/json")
    conn.putheader("Content-Length", "100000")
    conn.endheaders()
    conn.send(b"0123456789")
    response = conn.getresponse()
    body = json.loads(response.read())
    conn.close()
    assert (response.status, body["error"]["code"]) == (413, "payload_too_large")


def test_a_rejected_body_is_not_read_as_the_next_request(client, capsys):
    """Corpo recusado sem ser lido não pode sobrar na conexão keep-alive e virar a
    "requisição" seguinte; e o corpo nunca aparece no log."""
    conn = client.connection()
    conn.request(
        "POST", "/tables", body=b'{"campaign_id":"SEGREDO"}', headers={"Content-Type": "text/plain"}
    )
    response = conn.getresponse()
    response.read()
    assert response.status == 415
    conn.request("GET", "/campaigns")
    response = conn.getresponse()
    listed = json.loads(response.read())
    conn.close()
    assert response.status == 200
    assert listed[0]["id"] == "sombra-do-vale"
    assert "SEGREDO" not in capsys.readouterr().err


def test_authorization_header_is_case_insensitive(client, issued):
    _, created, _ = create(client)
    status, _, _ = client.call(
        "GET", f"/tables/{created['table_id']}", headers={"authorization": f"bearer {issued[-1]}"}
    )
    assert status == 200


def test_duplicated_or_unicode_content_length_is_refused(client):
    conn = client.connection()
    conn.putrequest("POST", "/tables")
    conn.putheader("Content-Type", "application/json")
    conn.putheader("Content-Length", "2")
    conn.putheader("Content-Length", "999")
    conn.endheaders()
    conn.send(b"{}")
    response = conn.getresponse()
    body = json.loads(response.read())
    conn.close()
    assert (response.status, body["error"]["code"]) == (400, "bad_request")

    conn = client.connection()
    conn.putrequest("POST", "/tables")
    conn.putheader("Content-Type", "application/json")
    conn.putheader("Content-Length", "\u00b2")  # "²": str.isdigit aceita, int() não
    conn.endheaders()
    response = conn.getresponse()
    body = json.loads(response.read())
    conn.close()
    assert (response.status, body["error"]["code"]) == (411, "length_required")


def test_short_body_times_out_without_a_traceback(client, monkeypatch, capsys):
    monkeypatch.setattr("devaneio.server.http.Handler.timeout", 0.3)
    conn = client.connection()
    conn.putrequest("POST", "/tables")
    conn.putheader("Content-Type", "application/json")
    conn.putheader("Content-Length", "50")
    conn.endheaders()
    conn.send(b"{")
    response = conn.getresponse()
    body = json.loads(response.read())
    conn.close()
    assert (response.status, body["error"]["code"]) == (408, "request_timeout")
    assert "Traceback" not in capsys.readouterr().err


@pytest.mark.parametrize("method", ["PUT", "DELETE", "PATCH", "OPTIONS"])
def test_methods_without_route_get_json_errors(client, method):
    status, body, headers = client.call(method, "/campaigns")
    assert (status, body["error"]["code"]) == (405, "method_not_allowed")
    assert headers["Cache-Control"] == "no-store"
    status, body, _ = client.call(method, "/nada")
    assert (status, body["error"]["code"]) == (404, "not_found")


def test_log_has_method_path_and_status_but_no_query_nor_headers(client, capsys):
    status, _, _ = client.call("GET", "/campaigns?senha=SEGREDO", auth="SEGREDO-TOKEN")
    assert status == 200
    err = capsys.readouterr().err
    assert '"GET /campaigns" 200' in err
    assert "SEGREDO" not in err


def test_unexpected_exception_is_a_generic_500_and_the_server_goes_on(
    client, service, monkeypatch, capsys
):
    def boom():
        raise RuntimeError("detalhe interno SEGREDO")

    monkeypatch.setattr(service, "list_campaigns", boom)
    status, body, _ = client.call("GET", "/campaigns")
    assert status == 500
    assert body == {"error": {"code": "internal", "message": "erro interno"}}
    assert "SEGREDO" not in json.dumps(body)
    assert "SEGREDO" in capsys.readouterr().err
    monkeypatch.undo()
    status, _, _ = client.call("GET", "/campaigns")
    assert status == 200


def test_unreadable_save_is_a_generic_500(client, service):
    _, created, _ = create(client)
    corrupt(service, created["table_id"], state='{"state": "SEGREDO"}')
    status, body, _ = client.call(
        "GET", f"/tables/{created['table_id']}", auth=created["host_token"]
    )
    assert (status, body["error"]["code"]) == (500, "internal")
    assert "SEGREDO" not in json.dumps(body)


def test_api_failure_from_the_service_keeps_its_status(client, service, monkeypatch):
    def refuse():
        raise ApiFailure(418, "teapot", "sou um bule")

    monkeypatch.setattr(service, "list_campaigns", refuse)
    status, body, _ = client.call("GET", "/campaigns")
    assert (status, body["error"]) == (418, {"code": "teapot", "message": "sou um bule"})


# --- python -m devaneio.server ------------------------------------------------


def main_args(tmp_path, *extra):
    return ["--campanhas", str(CAMPAIGN_PATH.parent), "--dados", str(tmp_path / "d"), *extra]


def interrupt(_self):
    raise KeyboardInterrupt


def test_main_refuses_a_bad_campaign_folder(tmp_path, capsys):
    folder = tmp_path / "c"
    folder.mkdir()
    (folder / "ruim.json").write_text("{", encoding="utf-8")
    assert main(["--campanhas", str(folder), "--dados", str(tmp_path / "d")]) == 1
    assert "campanha 'ruim.json' inválida" in capsys.readouterr().err


def test_main_refuses_a_bad_llm_configuration(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DEVANEIO_LLM_BASE_URL", "ftp://x")
    monkeypatch.setenv("DEVANEIO_LLM_MODEL", "qwen3")
    assert main(main_args(tmp_path)) == 1
    assert "erro: DEVANEIO_LLM_BASE_URL inválida" in capsys.readouterr().err


def test_main_on_loopback_prints_the_port_and_the_llm_without_warning(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("DEVANEIO_LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("DEVANEIO_LLM_MODEL", "qwen3")
    monkeypatch.setattr(ApiServer, "serve_forever", interrupt)
    assert main(main_args(tmp_path, "--porta", "0")) == 0
    out, err = capsys.readouterr()
    assert err == ""
    port = re.search(r"Devaneio: mesa em http://127\.0\.0\.1:(\d+) \(1 campanha\(s\)\)", out)
    assert port is not None
    assert int(port.group(1)) > 0
    assert "LLM ligado (qwen3 em localhost:11434)" in out
    assert "encerrando." in out


def test_main_sem_llm_ignores_the_environment(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DEVANEIO_LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("DEVANEIO_LLM_MODEL", "qwen3")
    monkeypatch.setattr(ApiServer, "serve_forever", interrupt)
    assert main(main_args(tmp_path, "--porta", "0", "--sem-llm")) == 0
    assert "LLM ligado" not in capsys.readouterr().out


class FakeServer:
    """Nada é escutado: só o que ``main`` faz em volta do servidor."""

    def __init__(self, host, port):
        self.server_address = (host, port or 4242)
        self.closed = False

    def serve_forever(self):
        raise KeyboardInterrupt

    def server_close(self):
        self.closed = True


def test_main_warns_on_stderr_when_listening_outside_loopback(tmp_path, monkeypatch, capsys):
    servers = []

    def fake_make_server(host, port, _service, _static=None, _editor=None):
        servers.append(FakeServer(host, port))
        return servers[-1]

    monkeypatch.setattr("devaneio.server.__main__.make_server", fake_make_server)
    assert main(main_args(tmp_path, "--host", "192.0.2.10", "--porta", "0")) == 0
    out, err = capsys.readouterr()
    assert "aviso: escutando em 192.0.2.10: HTTP em claro, inclusive tokens." in err
    assert "Devaneio: mesa em http://192.0.2.10:4242" in out
    assert [s.closed for s in servers] == [True]


@pytest.mark.parametrize("value", ["nan", "-1", "inf", "x", "-inf"])
def test_the_say_interval_flag_must_be_a_finite_non_negative_number(tmp_path, capsys, value):
    with pytest.raises(SystemExit) as info:
        main(
            [
                "--campanhas",
                str(CAMPAIGN_PATH.parent),
                "--dados",
                str(tmp_path / "d"),
                "--intervalo-say",
                value,
            ]
        )
    assert info.value.code == 2
    assert "--intervalo-say" in capsys.readouterr().err


@pytest.mark.parametrize(("raw", "expected"), [("0", 0.0), ("2.5", 2.5), ("30", 30.0)])
def test_the_say_interval_flag_reaches_the_service(tmp_path, monkeypatch, raw, expected):
    seen = []

    def spy(*_args, **kwargs):
        seen.append(kwargs["say_cooldown"])
        assert kwargs["llm_secrets"] is False  # sem a flag, os segredos não vão ao LLM

    monkeypatch.setattr("devaneio.server.__main__.TableService", spy)
    monkeypatch.setattr(
        "devaneio.server.__main__.make_server",
        lambda host, port, _service, _static=None, _editor=None: FakeServer(host, port),
    )
    assert main(main_args(tmp_path, "--porta", "0", "--intervalo-say", raw)) == 0
    assert seen == [expected]


def test_the_secrets_flag_reaches_the_service(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(
        "devaneio.server.__main__.TableService", lambda *_a, **kw: seen.append(kw["llm_secrets"])
    )
    monkeypatch.setattr(
        "devaneio.server.__main__.make_server",
        lambda host, port, _service, _static=None, _editor=None: FakeServer(host, port),
    )
    assert main(main_args(tmp_path, "--porta", "0", "--segredos-no-llm")) == 0
    assert seen == [True]


def test_the_talk_log_over_http(client):
    table_id, _, host, bia, _ = play_setup(client)
    status, view, _ = client.call("GET", f"/tables/{table_id}/events", auth=bia)
    assert status == 200
    assert view["talk"] == []
    assert isinstance(view["talk_seq"], int)
    far = view["talk_seq"] + 10**6  # 13 dígitos: o número de fala vem do relógio
    status, again, _ = client.call("GET", f"/tables/{table_id}/events?since_talk={far}", auth=host)
    assert status == 200
    assert again["talk"] == []


@pytest.mark.parametrize("value", ["-1", "x", "1.5", "9" * 17, "1&since_talk=2"])
def test_since_talk_must_be_a_non_negative_integer(client, value):
    table_id, _, _, bia, _ = play_setup(client)
    status, body, _ = client.call("GET", f"/tables/{table_id}/events?since_talk={value}", auth=bia)
    assert (status, body["error"]["code"]) == (400, "bad_request")


def test_the_chat_routes_over_http(client):
    table_id, _, host, bia, _ = play_setup(client)
    status, sent, _ = client.call(
        "POST", f"/tables/{table_id}/chat", body={"text": "bora pelas ruínas"}, auth=bia
    )
    assert status == 201
    assert (sent["seq"], sent["role"], sent["text"]) == (1, "player", "bora pelas ruínas")
    status, chat, _ = client.call("GET", f"/tables/{table_id}/chat?since=0", auth=host)
    assert status == 200
    assert [m["text"] for m in chat["messages"]] == ["bora pelas ruínas"]
    assert chat["chat_seq"] == 1
    status, view, _ = client.call("GET", f"/tables/{table_id}/events", auth=host)
    assert [m["text"] for m in view["chat"]] == ["bora pelas ruínas"]
    status, view, _ = client.call("GET", f"/tables/{table_id}/events?since_chat=1", auth=host)
    assert view["chat"] == []
    assert view["chat_seq"] == 1


def test_a_whisper_over_http_reaches_only_the_recipient(client):
    table_id, _, host, bia, _ = play_setup(client)
    _, table, _ = client.call("GET", f"/tables/{table_id}", auth=bia)
    host_id = next(p["id"] for p in table["players"] if p["role"] == "host")
    status, sent, _ = client.call(
        "POST", f"/tables/{table_id}/chat", body={"text": "psiu", "to": host_id}, auth=bia
    )
    assert status == 201
    assert sent["to"] == host_id
    assert sent["to_name"] == "Ana"
    _, mine, _ = client.call("GET", f"/tables/{table_id}/chat?since=0", auth=host)
    assert [m["text"] for m in mine["messages"]] == ["psiu"]
    status, bad, _ = client.call(
        "POST", f"/tables/{table_id}/chat", body={"text": "x", "to": "p99"}, auth=bia
    )
    assert (status, bad["error"]["code"]) == (422, "bad_recipient")


def test_the_chat_route_refuses_without_a_token_and_with_a_bad_body(client):
    table_id, _, _, bia, _ = play_setup(client)
    status, body, _ = client.call("POST", f"/tables/{table_id}/chat", body={"text": "oi"})
    assert (status, body["error"]["code"]) == (401, "unauthorized")
    for bad in (
        {"text": ""},
        {"text": "a\nb"},
        {"text": "x" * 501},
        {"text": "oi", "extra": 1},
        {},
    ):
        status, body, _ = client.call("POST", f"/tables/{table_id}/chat", body=bad, auth=bia)
        assert (status, body["error"]["code"]) == (400, "bad_request")


@pytest.mark.parametrize("value", ["-1", "x", "1.5", "9" * 17])
def test_since_chat_must_be_a_non_negative_integer(client, value):
    table_id, _, _, bia, _ = play_setup(client)
    status, body, _ = client.call("GET", f"/tables/{table_id}/events?since_chat={value}", auth=bia)
    assert (status, body["error"]["code"]) == (400, "bad_request")


def test_the_copilot_route_answers_the_host_only(tmp_path, issued):
    with FakeLlmServer(lambda _body: (200, "Pense na floresta.")) as fake:
        service = TableService(
            Catalog(CAMPAIGN_PATH.parent),
            make_storage(tmp_path / "mesas", max_tables=5),
            llm=LlmConfig(base_url=fake.base_url, model="m"),
            copilot_cooldown=0,
            token_source=lambda: issued.append(f"token-{next(TOKENS)}") or issued[-1],
            invite_source=lambda: "convite",
        )
        server = make_server("127.0.0.1", 0, service)
        thread = threading.Thread(
            target=lambda: server.serve_forever(poll_interval=0.02), daemon=True
        )
        thread.start()
        try:
            http = Client(f"http://127.0.0.1:{server.server_address[1]}", service)
            _, created, _ = create(http)
            table, host = created["table_id"], created["host_token"]
            _, joined, _ = http.call(
                "POST",
                f"/tables/{table}/players",
                body={"invite_code": "convite", "name": "Bia"},
            )
            path = f"/tables/{table}/copilot"
            status, body, headers = http.call("POST", path, body={"text": "e agora?"}, auth=host)
            assert (status, body) == (200, {"text": "Pense na floresta."})
            assert headers["Cache-Control"] == "no-store"
            status, body, _ = http.call(
                "POST", path, body={"text": "e agora?"}, auth=joined["token"]
            )
            assert (status, body["error"]["code"]) == (403, "forbidden")
            status, body, _ = http.call("POST", path, body={"text": "x" * 600}, auth=host)
            assert status == 400
            status, _, _ = http.call("GET", path, auth=host)
            assert status == 405
        finally:
            server.shutdown()
            server.server_close()


@pytest.mark.parametrize(("args", "expected"), [([], 5.0), (["--intervalo-copiloto", "12"], 12.0)])
def test_the_copilot_interval_flag_reaches_the_service(tmp_path, monkeypatch, args, expected):
    seen = []
    monkeypatch.setattr(
        "devaneio.server.__main__.TableService",
        lambda *_a, **kw: seen.append(kw["copilot_cooldown"]),
    )
    monkeypatch.setattr(
        "devaneio.server.__main__.make_server",
        lambda host, port, _service, _static=None, _editor=None: FakeServer(host, port),
    )
    assert main(main_args(tmp_path, "--porta", "0", *args)) == 0
    assert seen == [expected]


@pytest.mark.parametrize(
    ("headers", "raw", "status", "code"),
    [
        ({"Content-Type": "text/plain"}, b'{"text":"oi"}', 415, "unsupported_media_type"),
        ({"Content-Type": "application/json"}, b"", 400, "bad_request"),
        ({"Content-Type": "application/json"}, b'{"text":"oi","x":1}', 400, "bad_request"),
        ({"Content-Type": "application/json"}, b'{"text":"a\\u0007b"}', 400, "bad_request"),
    ],
    ids=["content-type", "sem-corpo", "campo-extra", "controle"],
)
def test_the_copilot_route_validates_the_body_before_anything_else(
    client, headers, raw, status, code
):
    table_id, _, host, _bia, _ = play_setup(client)
    path = f"/tables/{table_id}/copilot"
    got_status, body, _ = client.call("POST", path, raw=raw, headers=headers, auth=host)
    assert (got_status, body["error"]["code"]) == (status, code)


def test_the_copilot_route_without_content_type_is_415(client):
    table_id, _, host, _bia, _ = play_setup(client)
    conn = client.connection()
    conn.putrequest("POST", f"/tables/{table_id}/copilot")
    conn.putheader("Authorization", f"Bearer {host}")
    conn.putheader("Content-Length", "13")
    conn.endheaders(b'{"text":"oi"}')
    response = conn.getresponse()
    body = json.loads(response.read())
    conn.close()
    assert (response.status, body["error"]["code"]) == (415, "unsupported_media_type")


def test_the_rules_route_over_http(client, issued):
    _, created, _ = create(client)
    table, host = created["table_id"], created["host_token"]
    assert created["table"]["you"] == "p1"
    status, body, headers = client.call("GET", f"/tables/{table}/rules", auth=host)
    assert status == 200
    assert headers["Cache-Control"] == "no-store"
    assert body["id"] == "default"
    assert body["combat"] == {"default_weapon": "punhos", "fallen_can_act": False}
    assert client.call("GET", f"/tables/{table}/rules")[0] == 401
    assert client.call("GET", f"/tables/{'0' * 16}/rules", auth=host)[0] == 404
    assert client.call("POST", f"/tables/{table}/rules", body={}, auth=host)[0] == 405
    assert client.call("GET", f"/tables/{table}", auth=host)[1]["you"] == "p1"


def test_the_lifecycle_route_starts_pauses_and_ends_the_game(client):
    _, created, _ = create(client, lobby=True)
    table, host = created["table_id"], created["host_token"]
    path = f"/tables/{table}/lifecycle"
    status, body, _ = client.call("POST", path, body={"action": "start", "revision": 0}, auth=host)
    assert (status, body["error"]["code"]) == (409, "no_characters")
    _, result, _ = client.call(
        "POST",
        f"/tables/{table}/commands",
        body={"line": 'entrar ana "Ana"', "revision": 0},
        auth=host,
    )
    status, view, _ = client.call(
        "POST", path, body={"action": "start", "revision": result["revision"]}, auth=host
    )
    assert (status, view["phase"], view["role"]) == (200, "running", "host")
    status, body, _ = client.call(
        "POST", path, body={"action": "explodir", "revision": view["revision"]}, auth=host
    )
    assert (status, body["error"]["code"]) == (400, "bad_request")
    status, view, _ = client.call(
        "POST", path, body={"action": "pause", "revision": view["revision"]}, auth=host
    )
    assert (status, view["phase"]) == (200, "paused")
    status, _, _ = client.call("GET", path, auth=host)
    assert status == 405
    status, body, _ = client.call("POST", path, body={"action": "end", "revision": 0})
    assert (status, body["error"]["code"]) == (401, "unauthorized")
