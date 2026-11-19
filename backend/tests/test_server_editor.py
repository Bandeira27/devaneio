"""O editor de campanhas: segurança do lugar (Host, Origin, loopback), validação em português, escrita e prévia."""

import argparse
import contextlib
import http.client
import json
import os
import socket
import threading
from pathlib import Path

import pytest

from conftest import CAMPAIGN_PATH
from devaneio.server import ApiFailure, Catalog, Storage, TableService
from devaneio.server import http as server_http
from devaneio.server.__main__ import browser_url, project_root, resolve_folders
from devaneio.server.catalog import CatalogError
from devaneio.server.editor import (
    CAMPAIGN_ID,
    EditorService,
    host_allowed,
    is_loopback,
    origin_allowed,
    peer_is_local,
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


@pytest.mark.parametrize("address", ["127.0.0.1", "127.0.0.5", "::1", "::ffff:127.0.0.1", "::1%lo"])
def test_loopback_peers_are_this_machine(address):
    assert peer_is_local(address)


@pytest.mark.parametrize(
    "address",
    [
        "192.168.0.5",
        "10.0.0.1",
        "8.8.8.8",
        "::ffff:192.168.0.5",
        "fe80::1%eth0",
        "",
        "localhost",
        "x",
    ],
)
def test_other_peers_are_not_this_machine(address):
    # Nem o endereço da própria rede vale: o editor só atende por localhost.
    assert not peer_is_local(address)


def serve_on_the_network(setup):
    """Escuta em todas as interfaces, como ``--host 0.0.0.0``: o editor tem de seguir só da própria máquina."""
    catalog, storage, service = setup
    server = make_server("0.0.0.0", 0, service, None, EditorService(catalog, storage))  # noqa: S104 — teste do --host 0.0.0.0
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def test_listening_on_the_network_keeps_players_in_and_the_editor_local(setup):
    server = serve_on_the_network(setup)
    api = Api(server.server_address[1])
    try:
        # Um jogador entra pelo endereço da rede: o Host dele é o da rede, e a mesa responde.
        status, _ = api.call("GET", "/campaigns", headers={"Host": f"192.168.0.5:{api.port}"})
        assert status == 200
        # O anfitrião, por localhost, edita.
        assert api.call("GET", "/editor/campaigns")[0] == 200
        # Pelo endereço da rede o Host não é local: o editor recusa.
        status, body = api.call(
            "GET", "/editor/campaigns", headers={"Host": f"192.168.0.5:{api.port}"}
        )
        assert status == 403
        assert body["error"]["code"] == "host_not_allowed"
    finally:
        server.shutdown()
        server.server_close()


def test_a_simulated_peer_from_the_network_gets_404_in_the_editor_and_the_table_still_answers(
    setup, monkeypatch
):
    server = serve(setup)
    api = Api(server.server_address[1])
    # A origem de rede é simulada, depois de o servidor já ter decidido que escuta só aqui (`local_only`).
    monkeypatch.setattr(server_http, "peer_is_local", lambda _address: False)
    try:
        for method, path in [
            ("GET", "/editor/campaigns"),
            ("POST", "/editor/validate"),
            ("PUT", "/editor/campaigns/sombra-do-vale"),
            ("GET", "/editor"),
        ]:
            status, body = api.call(method, path, {} if method != "GET" else None)
            assert status == 404, (method, path)
            assert body["error"]["code"] == "not_found"
        assert api.call("GET", "/campaigns")[0] == 200
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.parametrize(
    "header",
    ["Forwarded", "X-Forwarded-For", "X-Forwarded-Host", "X-Forwarded-Proto", "X-Real-IP"],
)
def test_a_proxy_or_tunnel_in_front_hides_the_editor(api, header):
    status, body = api.call("GET", "/editor/campaigns", headers={header: "203.0.113.9"})
    assert status == 404
    assert body["error"]["code"] == "not_found"
    assert api.call("GET", "/campaigns", headers={header: "203.0.113.9"})[0] == 200


def test_the_editor_is_off_only_when_asked_and_everything_else_still_works(api_off):
    assert api_off.call("GET", "/editor/campaigns")[0] == 404
    assert api_off.call("GET", "/campaigns")[0] == 200


def test_the_default_folders_come_from_the_project_and_the_flags_win(tmp_path):
    project = tmp_path / "projeto"
    (project / "campaigns").mkdir(parents=True)
    (project / "backend").mkdir()
    build = project / "frontend" / "app" / "dist" / "devaneio" / "browser"
    build.mkdir(parents=True)
    (build / "index.html").write_text("<!doctype html>", encoding="utf-8")
    none = argparse.Namespace(campanhas=None, dados=None, web=None)

    assert resolve_folders(none, project) == (project / "campaigns", project / "mesas", build)
    # De dentro de backend/ (a pasta de baixo) também acha o projeto.
    inside = project / "backend"
    assert resolve_folders(none, inside) == (project / "campaigns", project / "mesas", build)
    given = argparse.Namespace(campanhas=Path("a"), dados=Path("b"), web=Path("c"))
    assert resolve_folders(given, project) == (Path("a"), Path("b"), Path("c"))


def test_without_a_project_the_folders_must_be_given(tmp_path):
    assert project_root(tmp_path) is None
    with pytest.raises(ValueError, match="--campanhas e --dados"):
        resolve_folders(argparse.Namespace(campanhas=None, dados=None, web=None), tmp_path)


def test_a_campaigns_folder_alone_is_not_the_project(tmp_path):
    (
        tmp_path / "campaigns"
    ).mkdir()  # qualquer pasta com esse nome: o editor não grava nela sem pedido
    assert project_root(tmp_path) is None


def test_without_a_build_the_app_is_left_out(tmp_path):
    (tmp_path / "campaigns").mkdir()
    (tmp_path / "backend").mkdir()
    folders = resolve_folders(argparse.Namespace(campanhas=None, dados=None, web=None), tmp_path)
    assert folders[2] is None


@pytest.mark.parametrize(
    ("host", "url"),
    [
        ("127.0.0.1", "http://localhost:8765"),
        ("localhost", "http://localhost:8765"),
        ("0.0.0.0", "http://localhost:8765"),  # noqa: S104 — endereço de escuta no teste
        ("::", "http://localhost:8765"),
        ("::1", "http://[::1]:8765"),
        ("fe80::1", "http://[fe80::1]:8765"),
        ("192.168.0.5", "http://192.168.0.5:8765"),
    ],
)
def test_the_browser_opens_on_localhost_whenever_the_server_is_on_this_machine(host, url):
    assert browser_url(host, 8765) == url


def test_with_the_editor_off_every_editor_route_is_404(api_off):
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


def test_a_foreign_host_header_is_refused_everywhere_when_listening_only_here(api):
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


# --- Catalog.register ----------------------------------------------------------------


def test_register_replaces_the_same_id_without_duplicating_the_summary(setup, folder):
    catalog, _, _ = setup
    data = campaign_json(folder, title="Renomeada")
    (folder / "sombra-do-vale.json").write_text(json.dumps(data), encoding="utf-8")
    catalog.register(folder / "sombra-do-vale.json")
    assert [s.title for s in catalog.summaries()] == ["Renomeada"]


def test_register_refuses_the_same_id_in_another_file(setup, folder):
    catalog, _, _ = setup
    (folder / "copia.json").write_text(json.dumps(campaign_json(folder)), encoding="utf-8")
    with pytest.raises(CatalogError, match="repetida"):
        catalog.register(folder / "copia.json")
    assert catalog.path("sombra-do-vale") == (folder / "sombra-do-vale.json").resolve()


def test_register_refuses_a_file_outside_the_catalog_folder(setup, folder, tmp_path):
    catalog, _, _ = setup
    outside = tmp_path / "fora.json"
    outside.write_text(json.dumps(campaign_json(folder, id="fora")), encoding="utf-8")
    with pytest.raises(CatalogError, match="pasta do catálogo"):
        catalog.register(outside)
    assert catalog.path("fora") is None


def test_register_refuses_a_subfolder_even_with_a_valid_campaign(setup, folder):
    catalog, _, _ = setup
    (folder / "sub").mkdir()
    (folder / "sub" / "x.json").write_text(
        json.dumps(campaign_json(folder, id="x")), encoding="utf-8"
    )
    with pytest.raises(CatalogError, match="pasta do catálogo"):
        catalog.register(folder / "sub" / "x.json")


def test_register_keeps_summaries_in_file_name_order(setup, folder):
    catalog, _, _ = setup
    (folder / "aaa.json").write_text(
        json.dumps(campaign_json(folder, id="aaa", title="A")), encoding="utf-8"
    )
    catalog.register(folder / "aaa.json")
    assert [s.id for s in catalog.summaries()] == ["aaa", "sombra-do-vale"]


# --- Storage.campaigns_in_use --------------------------------------------------------


def test_campaigns_in_use_ignores_corrupt_and_odd_saves(setup, folder):
    _, storage, service = setup
    service.create_table(CreateTableRequest(campaign_id="sombra-do-vale", host_name="Ana", seed=1))
    d = storage.data_dir
    (d / "0000000000000001.json").write_text("{não é json", encoding="utf-8")
    (d / "0000000000000002.json").write_text('{"sem": "caminho"}', encoding="utf-8")
    (d / "0000000000000003.json").write_text('{"campaign_path": 5}', encoding="utf-8")
    (d / "0000000000000004.json").write_text("[1]", encoding="utf-8")
    (d / "0000000000000005.json").write_bytes(b"\xff\xfe")
    (d / "notas.json").write_text('{"campaign_path": "x.json"}', encoding="utf-8")
    assert storage.campaigns_in_use() == {(folder / "sombra-do-vale.json").resolve()}


def test_a_corrupt_save_does_not_block_listing_or_updating(api, folder, setup):
    _, storage, _ = setup
    (storage.data_dir / "0000000000000001.json").write_text("{quebrado", encoding="utf-8")
    assert api.call("GET", "/editor/campaigns")[1][0]["writable"] is True
    status, _ = api.call(
        "PUT", "/editor/campaigns/sombra-do-vale", {"campaign": campaign_json(folder, title="Y")}
    )
    assert status == 200


# --- systems com sistema do autor quebrado -------------------------------------------


def test_systems_skip_a_broken_author_system_and_list_a_good_one(api, folder):
    (folder / "sistemas").mkdir()
    (folder / "sistemas" / "quebrado.json").write_text("{não é json", encoding="utf-8")
    (folder / "sistemas" / "Maiuscula.json").write_text("{}", encoding="utf-8")
    status, systems = api.call("GET", "/editor/systems")
    assert status == 200
    assert [s["id"] for s in systems] == ["default"]
    assert api.call("GET", "/editor/systems/quebrado")[0] == 404


def test_validate_names_a_broken_author_system_instead_of_crashing(api, folder):
    (folder / "sistemas").mkdir()
    (folder / "sistemas" / "quebrado.json").write_text("{não é json", encoding="utf-8")
    status, report = api.call(
        "POST", "/editor/validate", {"campaign": campaign_json(folder, rules_id="quebrado")}
    )
    assert status == 200
    assert report["ok"] is False
    assert any("quebrado" in e["message"] for e in report["errors"])


# --- 405 contra 404 e fechamento da conexão -------------------------------------------


def test_a_known_editor_path_with_the_wrong_method_is_405_and_an_unknown_one_is_404(api):
    for method, path in [
        ("DELETE", "/editor/campaigns"),
        ("PUT", "/editor/validate"),
        ("POST", "/editor/systems"),
        ("GET", "/editor/preview"),
    ]:
        status, body = api.call(method, path, {} if method != "GET" else None)
        assert status == 405, (method, path)
        assert body["error"]["code"] == "method_not_allowed"
    status, body = api.call("GET", "/editor/nada")
    assert status == 404
    assert body["error"]["code"] == "not_found"


def test_the_correct_method_still_reaches_a_path_that_has_two_methods(api, folder):
    assert api.call("GET", "/editor/campaigns/sombra-do-vale")[0] == 200
    status, _ = api.call(
        "PUT", "/editor/campaigns/sombra-do-vale", {"campaign": campaign_json(folder)}
    )
    assert status == 200


def raw_exchange(port, request: bytes) -> bytes:
    with socket.create_connection(("127.0.0.1", port), timeout=5) as sock:
        sock.sendall(request)
        chunks = []
        while True:
            data = sock.recv(65536)
            if not data:
                break
            chunks.append(data)
    return b"".join(chunks)


def test_a_refused_write_closes_the_connection_and_the_body_is_not_a_second_request(api):
    smuggled = b"GET /editor/campaigns HTTP/1.1\r\nHost: localhost:%d\r\n\r\n" % api.port
    request = (
        b"POST /editor/validate HTTP/1.1\r\nHost: evil.example\r\n"
        b"Content-Type: application/json\r\nContent-Length: %d\r\n\r\n" % len(smuggled)
    ) + smuggled
    reply = raw_exchange(api.port, request)  # termina só se o servidor fechar a conexão
    assert reply.count(b"HTTP/1.1 ") == 1
    assert b"403" in reply.split(b"\r\n", 1)[0]
    assert b"Connection: close" in reply


def test_a_405_on_a_post_without_reading_the_body_closes_the_connection(api):
    request = (
        b"POST /editor/systems HTTP/1.1\r\nHost: localhost:%d\r\n"
        b"Content-Type: application/json\r\nContent-Length: 2\r\n\r\n{}" % api.port
    )
    reply = raw_exchange(api.port, request)
    assert b" 405 " in reply.split(b"\r\n", 1)[0]
    assert reply.count(b"HTTP/1.1 ") == 1


# --- achados da revisão: surrogate, pedidos simultâneos, permissão, id com quebra de linha ----------


def test_text_that_cannot_be_encoded_is_refused_at_the_door_and_never_leaves_a_temp_file(
    api, folder, setup
):
    data = campaign_json(folder, id="surrogate", title="a\ud800b")
    status, _ = api.call(
        "POST", "/editor/campaigns", raw=json.dumps({"campaign": data}).encode("ascii")
    )
    assert status == 400  # o corpo JSON com surrogate solto nem chega ao serviço
    catalog, storage, _service = setup
    with pytest.raises(
        ApiFailure
    ) as caught:  # e, se chegasse, o serviço recusa sem deixar temporário
        EditorService(catalog, storage).create(data)
    assert caught.value.status == 422
    assert sorted(p.name for p in folder.iterdir()) == ["sombra-do-vale.json"]


def test_two_creates_of_the_same_id_at_once_write_one_and_refuse_the_other(api, folder):
    data = campaign_json(folder, id="corrida", title="Corrida")
    results = []

    def go():
        results.append(api.call("POST", "/editor/campaigns", {"campaign": data})[0])

    threads = [threading.Thread(target=go) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == [201, 409, 409, 409, 409, 409]
    assert not list(folder.glob(".editor-*"))


def test_a_rewritten_campaign_keeps_its_permission(api, folder):
    path = folder / "sombra-do-vale.json"
    path.chmod(0o664)
    api.call(
        "PUT", "/editor/campaigns/sombra-do-vale", {"campaign": campaign_json(folder, title="X")}
    )
    assert path.stat().st_mode & 0o777 == 0o664
    api.call("POST", "/editor/campaigns", {"campaign": campaign_json(folder, id="nova", title="N")})
    assert (folder / "nova.json").stat().st_mode & 0o777 == 0o644


def test_an_id_with_a_trailing_newline_is_not_a_slug():
    assert CAMPAIGN_ID.fullmatch("abc")
    assert not CAMPAIGN_ID.fullmatch("abc\n")
