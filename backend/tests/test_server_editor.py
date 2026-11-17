"""O editor de campanhas: segurança do lugar (Host, Origin, loopback), validação em português, escrita e prévia."""

import contextlib
import http.client
import json
import os
import threading
from pathlib import Path

import pytest

from conftest import CAMPAIGN_PATH
from devaneio.server import Catalog, Storage, TableService
from devaneio.server.__main__ import main
from devaneio.server.editor import (
    EditorService,
    host_allowed,
    is_loopback,
    origin_allowed,
)
from devaneio.server.http import make_server
from devaneio.server.models import CreateTableRequest

SECRET = "SEGREDO-DO-SACERDOTE"  # noqa: S105 — texto de teste, não é senha


class Api:
    """Cliente cru: deixa mandar `Host` e `Origin` à mão."""

    def __init__(self, port: int):
        self.port = port

    def call(self, method, path, body=None, *, headers=None, raw=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        hdrs = {"Host": f"localhost:{self.port}", **(headers or {})}
        data = raw
        if body is not None:
            data = json.dumps(body).encode()
        if data is not None:
            hdrs.setdefault("Content-Type", "application/json")
        # O servidor pode recusar o corpo e fechar antes de recebê-lo todo: a resposta já está a caminho.
        with contextlib.suppress(BrokenPipeError, ConnectionResetError):
            connection.request(method, path, body=data, headers=hdrs)
        response = connection.getresponse()
        payload = json.loads(response.read() or b"null")
        connection.close()
        return response.status, payload


@pytest.fixture
def folder(tmp_path):
    root = tmp_path / "campanhas"
    root.mkdir()
    data = json.loads(CAMPAIGN_PATH.read_text(encoding="utf-8"))
    data["npcs"][0]["private_notes"] = [SECRET]
    (root / "sombra-do-vale.json").write_text(json.dumps(data), encoding="utf-8")
    return root


@pytest.fixture
def setup(folder, tmp_path):
    catalog = Catalog(folder)
    storage = Storage(tmp_path / "mesas", max_tables=10)
    service = TableService(catalog, storage)
    return catalog, storage, service


def serve(setup, *, editor=True):
    catalog, storage, service = setup
    server = make_server(
        "127.0.0.1", 0, service, None, EditorService(catalog, storage) if editor else None
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


@pytest.fixture
def api(setup):
    server = serve(setup)
    yield Api(server.server_address[1])
    server.shutdown()
    server.server_close()


@pytest.fixture
def api_off(setup):
    server = serve(setup, editor=False)
    yield Api(server.server_address[1])
    server.shutdown()
    server.server_close()


def campaign_json(folder: Path, **over) -> dict:
    data = json.loads((folder / "sombra-do-vale.json").read_text(encoding="utf-8"))
    data.update(over)
    return data


# --- o lugar: loopback, Host e Origin ------------------------------------------------


@pytest.mark.parametrize("host", ["127.0.0.1", "::1", "localhost", " LOCALHOST "])
def test_loopback_hosts(host):
    assert is_loopback(host)


@pytest.mark.parametrize("host", ["10.0.0.1", "192.168.0.5", "example.com", "", "::"])
def test_other_hosts_are_not_loopback(host):
    assert not is_loopback(host)


@pytest.mark.parametrize(
    ("header", "port", "allowed"),
    [
        ("localhost:8765", 8765, True),
        ("127.0.0.1:8765", 8765, True),
        ("[::1]:8765", 8765, True),
        ("LOCALHOST:8765", 8765, True),
        ("localhost", 80, True),
        ("localhost", 8765, False),
        ("localhost:9999", 8765, False),
        ("evil.example:8765", 8765, False),
        ("localhost.evil.example:8765", 8765, False),
        ("127.0.0.1.evil.example:8765", 8765, False),
        ("[::1]x:8765", 8765, False),
        ("localhost:8765x", 8765, False),
        ("", 8765, False),
        (None, 8765, False),
    ],
)
def test_host_header_must_be_local_with_our_port(header, port, allowed):
    assert host_allowed(header, port) is allowed


def test_origin_must_be_ourselves_when_present():
    assert origin_allowed(None, "localhost:1")
    assert origin_allowed("http://localhost:1", "localhost:1")
    assert not origin_allowed("http://evil.example", "localhost:1")
    assert not origin_allowed("null", "localhost:1")
    assert not origin_allowed("https://localhost:1", "localhost:1")


def test_the_server_refuses_to_start_the_editor_outside_loopback(folder, tmp_path, capsys):
    code = main(
        [
            "--campanhas",
            str(folder),
            "--dados",
            str(tmp_path / "d"),
            "--editor",
            "--host",
            "192.168.0.5",
        ]
    )
    assert code == 1
    assert "loopback" in capsys.readouterr().err


def test_without_the_editor_flag_every_editor_route_is_404(api_off):
    for method, path in [
        ("GET", "/editor/campaigns"),
        ("POST", "/editor/campaigns"),
        ("PUT", "/editor/campaigns/sombra-do-vale"),
        ("POST", "/editor/validate"),
        ("GET", "/editor/systems"),
        ("GET", "/editor"),
    ]:
        status, body = api_off.call(method, path, {} if method != "GET" else None)
        assert status == 404, (method, path)
        assert body["error"]["code"] == "not_found"


def test_a_foreign_host_header_is_refused_everywhere_when_the_editor_is_on(api):
    for host in ("evil.example", f"localhost:{api.port + 1}", "localhost.evil.example"):
        for path in ("/editor/campaigns", "/campaigns"):
            status, body = api.call("GET", path, headers={"Host": f"{host}"})
            assert status == 403, (host, path)
            assert body["error"]["code"] == "host_not_allowed"


def test_a_foreign_origin_cannot_write(api, folder):
    body = {"campaign": campaign_json(folder, id="nova", title="Nova")}
    status, payload = api.call(
        "POST", "/editor/campaigns", body, headers={"Origin": "http://evil.example"}
    )
    assert status == 403
    assert payload["error"]["code"] == "origin_not_allowed"
    assert not (folder / "nova.json").exists()
    own = f"http://localhost:{api.port}"
    assert api.call("POST", "/editor/campaigns", body, headers={"Origin": own})[0] == 201


# --- ler -----------------------------------------------------------------------------


def test_list_get_and_systems(api, folder):
    status, listed = api.call("GET", "/editor/campaigns")
    assert status == 200
    assert listed == [{"id": "sombra-do-vale", "title": "A Sombra do Vale", "writable": True}]
    status, campaign = api.call("GET", "/editor/campaigns/sombra-do-vale")
    assert status == 200
    assert campaign["id"] == "sombra-do-vale"
    assert campaign["npcs"][0]["private_notes"] == [SECRET]  # o autor vê tudo
    assert api.call("GET", "/editor/campaigns/nao-existe")[0] == 404
    status, systems = api.call("GET", "/editor/systems")
    assert status == 200
    assert systems[0]["id"] == "default"
    status, rules = api.call("GET", "/editor/systems/default")
    assert status == 200
    assert rules["skills"]
    assert api.call("GET", "/editor/systems/nao-existe")[0] == 404


@pytest.mark.parametrize("bad", ["..%2Fx", "Sombra", "a%20b", "x" * 70, "%2e%2e", "a%00b"])
def test_an_id_that_is_not_a_slug_never_reaches_the_disk(api, bad):
    assert api.call("GET", f"/editor/campaigns/{bad}")[0] == 404
    assert api.call("PUT", f"/editor/campaigns/{bad}", {"campaign": {}})[0] == 404
    assert api.call("GET", f"/editor/systems/{bad}")[0] == 404


def test_a_campaign_with_a_table_is_not_writable(api, setup):
    _, _, service = setup
    service.create_table(CreateTableRequest(campaign_id="sombra-do-vale", host_name="Ana", seed=1))
    _status, listed = api.call("GET", "/editor/campaigns")
    assert listed[0]["writable"] is False


# --- validar -------------------------------------------------------------------------


def test_a_valid_campaign_has_no_errors(api, folder):
    status, report = api.call("POST", "/editor/validate", {"campaign": campaign_json(folder)})
    assert status == 200
    assert report["ok"] is True
    assert report["errors"] == []


def test_structure_errors_come_in_portuguese_with_the_field_path(api, folder):
    data = campaign_json(folder, title=3)
    data["locations"][1]["name"] = None
    data["beats"][0]["activate_when"] = [{"kind": "at_location"}]
    status, report = api.call("POST", "/editor/validate", {"campaign": data})
    assert status == 200
    assert report["ok"] is False
    by_path = {e["path"]: e["message"] for e in report["errors"]}
    assert by_path["title"] == "'title' precisa ser um texto"
    assert "locations.1.name" in by_path
    assert by_path["beats.0.activate_when.0.location_id"] == "falta preencher 'location_id'"
    assert all("Field required" not in m and "Input should" not in m for m in by_path.values())


def test_integrity_errors_say_which_id_is_broken(api, folder):
    data = campaign_json(folder)
    data["locations"][0]["connections"] = ["fantasma"]
    _status, report = api.call("POST", "/editor/validate", {"campaign": data})
    assert report["ok"] is False
    assert any(
        "fantasma" in e["message"] and "não existe" in e["message"] for e in report["errors"]
    )


def test_an_unknown_rules_system_is_an_error_not_a_crash(api, folder):
    status, report = api.call(
        "POST", "/editor/validate", {"campaign": campaign_json(folder, rules_id="inexistente")}
    )
    assert status == 200
    assert report["ok"] is False
    assert any("inexistente" in e["message"] for e in report["errors"])


def test_authoring_findings_come_with_the_report(api, folder):
    data = campaign_json(folder)
    data["beats"][0]["activate_when"] = [
        {"kind": "check_passed", "skill_id": "habilidade-fantasma"}
    ]
    _status, report = api.call("POST", "/editor/validate", {"campaign": data})
    assert report["ok"] is True  # estruturalmente certa
    assert any(
        f["level"] == "erro" and "habilidade-fantasma" in f["text"] for f in report["findings"]
    )


def test_a_body_over_the_editor_limit_is_413_and_a_normal_campaign_is_not(api, folder):
    status, _body = api.call("POST", "/editor/validate", raw=b"{" + b" " * (512 * 1024 + 1) + b"}")
    assert status == 413
    assert api.call("POST", "/editor/validate", {"campaign": campaign_json(folder)})[0] == 200


# --- gravar --------------------------------------------------------------------------


def test_create_writes_a_slug_named_file_and_the_catalog_sees_it_at_once(api, folder):
    data = campaign_json(folder, id="aventura-nova", title="Aventura Nova")
    status, created = api.call("POST", "/editor/campaigns", {"campaign": data})
    assert status == 201
    assert created == {"id": "aventura-nova", "title": "Aventura Nova", "writable": True}
    written = json.loads((folder / "aventura-nova.json").read_text(encoding="utf-8"))
    assert written["title"] == "Aventura Nova"
    status, catalog = api.call("GET", "/campaigns")
    assert {c["id"] for c in catalog} == {"sombra-do-vale", "aventura-nova"}
    assert not list(folder.glob(".editor-*"))  # nenhum temporário sobrou


def test_create_refuses_an_existing_id_and_an_invalid_campaign(api, folder):
    status, body = api.call("POST", "/editor/campaigns", {"campaign": campaign_json(folder)})
    assert status == 409
    assert body["error"]["code"] == "campaign_exists"
    broken = campaign_json(folder, id="quebrada")
    broken["locations"][0]["connections"] = ["fantasma"]
    status, body = api.call("POST", "/editor/campaigns", {"campaign": broken})
    assert status == 422
    assert body["error"]["code"] == "campaign_invalid"
    assert not (folder / "quebrada.json").exists()


@pytest.mark.parametrize("bad_id", ["../fora", "A", "a/b", "", "a b", "x" * 70])
def test_create_never_writes_outside_the_folder(api, folder, bad_id):
    status, _ = api.call(
        "POST", "/editor/campaigns", {"campaign": campaign_json(folder, id=bad_id)}
    )
    assert status == 422
    assert not (folder.parent / "fora.json").exists()
    assert sorted(p.name for p in folder.iterdir()) == ["sombra-do-vale.json"]


def test_update_rewrites_a_campaign_without_tables_and_keeps_the_id(api, folder):
    data = campaign_json(folder, title="Outro título")
    status, updated = api.call("PUT", "/editor/campaigns/sombra-do-vale", {"campaign": data})
    assert status == 200
    assert updated["title"] == "Outro título"
    assert (
        json.loads((folder / "sombra-do-vale.json").read_text(encoding="utf-8"))["title"]
        == "Outro título"
    )
    assert api.call("GET", "/campaigns")[1][0]["title"] == "Outro título"
    status, body = api.call(
        "PUT", "/editor/campaigns/sombra-do-vale", {"campaign": campaign_json(folder, id="outro")}
    )
    assert status == 409
    assert body["error"]["code"] == "campaign_id_changed"


def test_update_refuses_a_campaign_that_has_a_table(api, folder, setup):
    _, _, service = setup
    service.create_table(CreateTableRequest(campaign_id="sombra-do-vale", host_name="Ana", seed=1))
    before = (folder / "sombra-do-vale.json").read_text(encoding="utf-8")
    status, body = api.call(
        "PUT", "/editor/campaigns/sombra-do-vale", {"campaign": campaign_json(folder, title="X")}
    )
    assert status == 409
    assert body["error"]["code"] == "campaign_in_use"
    assert "cópia" in body["error"]["message"]
    assert (folder / "sombra-do-vale.json").read_text(encoding="utf-8") == before


def test_a_failed_write_leaves_the_original_and_no_temp_file(api, folder, monkeypatch):
    before = (folder / "sombra-do-vale.json").read_text(encoding="utf-8")

    def boom(*_args, **_kwargs):
        raise OSError("disco cheio")

    monkeypatch.setattr(os, "replace", boom)
    status, body = api.call(
        "PUT", "/editor/campaigns/sombra-do-vale", {"campaign": campaign_json(folder, title="X")}
    )
    assert status == 500
    assert body["error"]["code"] == "internal"
    assert "disco" not in json.dumps(body)  # o detalhe do sistema não vai ao cliente
    assert (folder / "sombra-do-vale.json").read_text(encoding="utf-8") == before
    assert not list(folder.glob(".editor-*"))


# --- prévia --------------------------------------------------------------------------


def test_the_preview_shows_the_secret_only_where_it_would_really_go(api, folder):
    status, preview = api.call("POST", "/editor/preview", {"campaign": campaign_json(folder)})
    assert status == 200
    assert SECRET not in json.dumps(preview["player"])
    assert SECRET not in preview["llm"]
    assert SECRET in preview["llm_secrets"]
    assert preview["player"]["title"] == "A Sombra do Vale"
    assert preview["copilot_chars"] > 0
    assert preview["copilot_limit"] == 60_000


def test_the_preview_of_an_invalid_campaign_is_refused_and_writes_nothing(api, folder):
    broken = campaign_json(folder)
    broken["locations"][0]["connections"] = ["fantasma"]
    assert api.call("POST", "/editor/preview", {"campaign": broken})[0] == 422
    assert sorted(p.name for p in folder.iterdir()) == ["sombra-do-vale.json"]
