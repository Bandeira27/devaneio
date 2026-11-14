"""Servidor HTTP em processo (porta 0) e cliente urllib: rotas, limites e erros."""

import http.client
import json
import re
import threading
import urllib.error
import urllib.request
from itertools import count

import pytest

from conftest import CAMPAIGN_PATH
from devaneio.server import ApiFailure, Catalog, Storage, TableService
from devaneio.server.__main__ import main
from devaneio.server.http import ApiServer, make_server

TOKENS = count(1)


class Client:
    def __init__(self, base_url):
        self.base_url = base_url

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
        Storage(tmp_path / "mesas", max_tables=5),
        token_source=issue,
        invite_source=lambda: "convite",
    )


@pytest.fixture
def client(service):
    server = make_server("127.0.0.1", 0, service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield Client(f"http://127.0.0.1:{server.server_address[1]}")
    finally:
        server.shutdown()
        server.server_close()


def create(client, **fields):
    body = {"campaign_id": "sombra-do-vale", "host_name": "Ana", "seed": 7, **fields}
    return client.call("POST", "/tables", body=body)


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

    status, created, headers = create(client)
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
    assert view["players"] == [{"id": "p1", "name": "Ana", "role": "host", "character_ids": []}]
    assert "hash" not in json.dumps(view)

    status, campaign, _ = client.call("GET", f"/tables/{table_id}/campaign", auth=token)
    assert status == 200
    assert campaign["id"] == "sombra-do-vale"


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
        ({"Content-Type": "application/json"}, b"x" * (64 * 1024 + 1), 413, "payload_too_large"),
        ({"Content-Type": "application/json"}, b"{not json", 400, "bad_request"),
        (
            {"Content-Type": "application/json", "Transfer-Encoding": "chunked"},
            b"{}",
            400,
            "bad_request",
        ),
    ],
    ids=["content-type", "tamanho", "json-invalido", "transfer-encoding"],
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
    path = service.storage.path_for(created["table_id"])
    path.write_text('{"save_version": 1, "campaign_path": "x.json", "state": "SEGREDO"}')
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

    def fake_make_server(host, port, _service):
        servers.append(FakeServer(host, port))
        return servers[-1]

    monkeypatch.setattr("devaneio.server.__main__.make_server", fake_make_server)
    assert main(main_args(tmp_path, "--host", "192.0.2.10", "--porta", "0")) == 0
    out, err = capsys.readouterr()
    assert "aviso: escutando em 192.0.2.10: HTTP em claro, inclusive tokens." in err
    assert "Devaneio: mesa em http://192.0.2.10:4242" in out
    assert [s.closed for s in servers] == [True]
