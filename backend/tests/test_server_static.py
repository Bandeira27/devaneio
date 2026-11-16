"""O front servido pelo próprio servidor: arquivos confinados, tipos fechados e cabeçalhos de navegador."""

import http.client
import json
import threading
from pathlib import Path

import pytest

from conftest import CAMPAIGN_PATH
from devaneio.server import Catalog, Storage, TableService
from devaneio.server.__main__ import main
from devaneio.server.http import make_server
from devaneio.server.static import CSP, MAX_STATIC_BYTES, StaticError, StaticSite

HASHED_JS = "main-3F8K2LQA.js"


@pytest.fixture
def web(tmp_path):
    root = tmp_path / "web"
    (root / "media").mkdir(parents=True)
    (root / "index.html").write_text("<!doctype html><title>mesa</title>", encoding="utf-8")
    (root / HASHED_JS).write_text("console.log('oi');", encoding="utf-8")
    (root / "styles-9ZK3H2PQ.css").write_text("body{}", encoding="utf-8")
    (root / "favicon.ico").write_bytes(b"\x00\x00\x01\x00")
    (root / "media" / "fonte-AB12CD34.woff2").write_bytes(b"wOF2")
    (root / "main.js.map").write_text("{}", encoding="utf-8")
    (root / ".segredo.txt").write_text("oculto", encoding="utf-8")
    (root / "script.py").write_text("print(1)", encoding="utf-8")
    (tmp_path / "fora.txt").write_text("fora da pasta", encoding="utf-8")
    (root / "ligacao.txt").symlink_to(tmp_path / "fora.txt")
    (root / "logo-devaneio.svg").write_text(
        "<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8"
    )
    (root / "dentro.txt").write_text("dentro", encoding="utf-8")
    (root / "interno.js").symlink_to(root / "main.js.map")
    (root / "oculto.txt").symlink_to(root / ".segredo.txt")
    (root / "apelido.txt").symlink_to(root / "dentro.txt")
    return root


def fetch(server, method, path, *, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
    try:
        conn.request(method, path, headers=headers or {})
        response = conn.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        conn.close()


@pytest.fixture
def server(tmp_path, web):
    service = TableService(
        Catalog(CAMPAIGN_PATH.parent),
        Storage(tmp_path / "mesas", max_tables=2),
        token_source=lambda: "token-x",
        invite_source=lambda: "convite-x",
    )
    httpd = make_server("127.0.0.1", 0, service, StaticSite(web))
    thread = threading.Thread(target=lambda: httpd.serve_forever(poll_interval=0.02), daemon=True)
    thread.start()
    try:
        yield httpd
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_the_root_serves_index_html_with_browser_security_headers(server):
    status, headers, body = fetch(server, "GET", "/")
    assert status == 200
    assert body == b"<!doctype html><title>mesa</title>"
    assert headers["Content-Type"] == "text/html; charset=utf-8"
    assert headers["Content-Security-Policy"] == CSP
    assert headers["Referrer-Policy"] == "no-referrer"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Cache-Control"] == "no-cache"
    assert fetch(server, "GET", "/index.html")[2] == body


def test_the_csp_blocks_inline_scripts_and_other_origins():
    assert "script-src 'self'" in CSP
    assert "'unsafe-inline'" not in CSP.split("script-src")[1].split(";")[0]
    assert "default-src 'self'" in CSP
    assert "frame-ancestors 'none'" in CSP
    assert "object-src 'none'" in CSP
    assert "connect-src 'self'" in CSP


@pytest.mark.parametrize(
    ("path", "content_type"),
    [
        (f"/{HASHED_JS}", "text/javascript; charset=utf-8"),
        ("/styles-9ZK3H2PQ.css", "text/css; charset=utf-8"),
        ("/media/fonte-AB12CD34.woff2", "font/woff2"),
        ("/favicon.ico", "image/x-icon"),
    ],
)
def test_assets_have_their_type_and_files_with_a_hash_are_immutable(server, path, content_type):
    status, headers, _ = fetch(server, "GET", path)
    assert status == 200
    assert headers["Content-Type"] == content_type
    expected = "no-cache" if path == "/favicon.ico" else "public, max-age=31536000, immutable"
    assert headers["Cache-Control"] == expected
    assert headers["Content-Security-Policy"] == CSP


def test_a_long_lowercase_word_in_the_name_is_not_a_hash(server):
    status, headers, _ = fetch(server, "GET", "/logo-devaneio.svg")
    assert status == 200
    assert headers["Cache-Control"] == "no-cache"  # nunca um ano de immutable por engano


def test_a_file_that_grows_past_the_limit_after_the_lookup_is_still_refused(
    server, web, monkeypatch
):
    monkeypatch.setattr("devaneio.server.http.MAX_STATIC_BYTES", 5)
    status, _, body = fetch(server, "GET", f"/{HASHED_JS}")
    assert status == 404
    assert json.loads(body)["error"]["code"] == "not_found"


def test_a_file_that_vanishes_after_the_lookup_is_a_404(server, web, monkeypatch):
    real_open = Path.open

    def vanishing(self, *args, **kwargs):
        if self.name == HASHED_JS:
            raise FileNotFoundError(str(self))
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", vanishing)
    assert fetch(server, "GET", f"/{HASHED_JS}")[0] == 404


def test_a_leading_double_slash_is_normalized_by_the_stdlib_and_stays_confined(server):
    """``http.server`` troca ``//x`` por ``/x`` antes de o handler ver o caminho: nunca vira host."""
    assert fetch(server, "GET", "//index.html")[0] == 200
    assert fetch(server, "GET", "///index.html")[0] == 200
    assert fetch(server, "GET", "//../fora.txt")[0] == 404
    assert fetch(server, "GET", "//etc/passwd")[0] == 404


def test_head_does_not_read_the_file_and_still_has_the_right_length(server, web, monkeypatch):
    def no_reading(self, *args, **kwargs):
        raise AssertionError("HEAD não deve abrir o arquivo")

    monkeypatch.setattr(Path, "open", no_reading)
    status, headers, body = fetch(server, "HEAD", f"/{HASHED_JS}")
    assert (status, body) == (200, b"")
    assert headers["Content-Length"] == str((web / HASHED_JS).stat().st_size)


def test_head_has_the_headers_and_no_body(server):
    _, get_headers, get_body = fetch(server, "GET", f"/{HASHED_JS}")
    status, headers, body = fetch(server, "HEAD", f"/{HASHED_JS}")
    assert (status, body) == (200, b"")
    assert headers["Content-Length"] == get_headers["Content-Length"] == str(len(get_body))
    assert headers["Content-Type"] == get_headers["Content-Type"]


@pytest.mark.parametrize(
    "path",
    [
        "/../fora.txt",
        "/%2e%2e/fora.txt",
        "/%2E%2E/fora.txt",
        "/media/../../fora.txt",
        "/media/%2e%2e/%2e%2e/fora.txt",
        "/..%2ffora.txt",
        "/%2e%2e%2ffora.txt",
        "/%252e%252e/fora.txt",
        "/..%5cfora.txt",
        "/media\\..\\..\\fora.txt",
        "/index.html%00.js",
        "/%00",
        "/ligacao.txt",
        "/interno.js",
        "/oculto.txt",
        "/.segredo.txt",
        "/%2esegredo.txt",
        "/media",
        "/media/",
        "//fora.txt",
        "/main.js.map",
        "/script.py",
        "/nao-existe.js",
        "/%ff.js",
    ],
)
def test_nothing_outside_the_build_is_ever_served(server, path):
    status, headers, body = fetch(server, "GET", path)
    assert status == 404, path
    assert json.loads(body)["error"]["code"] == "not_found"
    assert b"fora da pasta" not in body
    assert headers["Content-Type"].startswith("application/json")


def test_a_symlink_that_stays_inside_the_folder_is_fine(server):
    status, _, body = fetch(server, "GET", "/apelido.txt")
    assert (status, body) == (200, b"dentro")


def test_the_api_always_wins_over_files_and_keeps_its_json_errors(server):
    status, headers, body = fetch(server, "GET", "/campaigns")
    assert status == 200
    assert headers["Content-Type"].startswith("application/json")
    assert "Content-Security-Policy" not in headers
    assert headers["Cache-Control"] == "no-store"
    assert [c["id"] for c in json.loads(body)] == ["sombra-do-vale"]
    status, _, body = fetch(server, "GET", "/tables")  # rota de API com método errado
    assert (status, json.loads(body)["error"]["code"]) == (405, "method_not_allowed")


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
def test_only_get_and_head_reach_the_files(server, method):
    status, _, body = fetch(server, method, "/index.html")
    assert status == 404
    assert json.loads(body)["error"]["code"] == "not_found"


def test_without_the_flag_the_server_is_json_only(tmp_path):
    service = TableService(Catalog(CAMPAIGN_PATH.parent), Storage(tmp_path / "m", max_tables=1))
    httpd = make_server("127.0.0.1", 0, service)
    thread = threading.Thread(target=lambda: httpd.serve_forever(poll_interval=0.02), daemon=True)
    thread.start()
    try:
        status, _, body = fetch(httpd, "GET", "/")
        assert (status, json.loads(body)["error"]["code"]) == (404, "not_found")
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_head_on_an_api_route_has_no_body(server):
    status, headers, body = fetch(server, "HEAD", "/nada")
    assert (status, body) == (404, b"")
    assert int(headers["Content-Length"]) > 0


def test_a_file_over_the_limit_is_not_served(server, web, monkeypatch):
    monkeypatch.setattr("devaneio.server.static.MAX_STATIC_BYTES", 10)
    assert fetch(server, "GET", f"/{HASHED_JS}")[0] == 404
    assert MAX_STATIC_BYTES > 10


def test_an_empty_file_is_served_with_length_zero(server, web):
    (web / "vazio.txt").write_bytes(b"")
    status, headers, body = fetch(server, "GET", "/vazio.txt")
    assert (status, body) == (200, b"")
    assert headers["Content-Length"] == "0"
    assert headers["Content-Type"] == "text/plain; charset=utf-8"


@pytest.mark.parametrize(
    ("name", "content_type"),
    [
        ("app.webmanifest", "application/manifest+json"),
        ("logo-devaneio.svg", "image/svg+xml"),
        ("fonte.woff2", "font/woff2"),
        ("logo.png", "image/png"),
        ("chunk.mjs", "text/javascript; charset=utf-8"),
    ],
)
def test_every_listed_extension_has_its_content_type(server, web, name, content_type):
    (web / name).write_bytes(b"x")
    status, headers, _ = fetch(server, "GET", f"/{name}")
    assert status == 200
    assert headers["Content-Type"] == content_type
    assert headers["X-Content-Type-Options"] == "nosniff"


def test_an_uppercase_extension_is_served_with_the_type_of_the_lowercase_one(server, web):
    (web / "LOGO.SVG").write_bytes(b"<svg/>")
    status, headers, _ = fetch(server, "GET", "/LOGO.SVG")
    assert status == 200
    assert headers["Content-Type"] == "image/svg+xml"


def test_an_uppercase_map_extension_is_still_refused(server, web):
    (web / "main.JS.MAP").write_text("{}", encoding="utf-8")
    assert fetch(server, "GET", "/main.JS.MAP")[0] == 404


def test_the_query_string_does_not_change_which_file_is_served(server):
    status, headers, body = fetch(server, "GET", "/index.html?x=1")
    assert status == 200
    assert body == b"<!doctype html><title>mesa</title>"
    assert headers["Cache-Control"] == "no-cache"
    assert fetch(server, "GET", "/?x=1&y=2")[2] == body
    assert fetch(server, "GET", f"/{HASHED_JS}?v=2")[0] == 200


def test_a_query_string_cannot_smuggle_a_path(server):
    assert fetch(server, "GET", "/nao-existe.js?/index.html")[0] == 404
    assert fetch(server, "GET", "/?../fora.txt")[2] == b"<!doctype html><title>mesa</title>"


def test_head_on_index_html_keeps_the_revalidation_and_the_security_headers(server):
    _, get_headers, _ = fetch(server, "GET", "/index.html")
    status, headers, body = fetch(server, "HEAD", "/index.html")
    assert (status, body) == (200, b"")
    assert headers["Cache-Control"] == "no-cache"
    for name in (
        "Content-Security-Policy",
        "Referrer-Policy",
        "X-Frame-Options",
        "X-Content-Type-Options",
        "Content-Type",
    ):
        assert headers[name] == get_headers[name]


def test_head_on_a_hashed_file_is_immutable(server):
    headers = fetch(server, "HEAD", f"/{HASHED_JS}")[1]
    assert headers["Cache-Control"] == "public, max-age=31536000, immutable"


@pytest.mark.parametrize("path", ["/media//fonte-AB12CD34.woff2", "//media//fonte-AB12CD34.woff2"])
def test_repeated_slashes_in_the_middle_of_the_path_are_not_a_file(server, path):
    assert fetch(server, "GET", path)[0] == 404


def test_a_very_long_path_is_a_404_and_not_a_crash(server):
    status, _, body = fetch(server, "GET", "/" + "a" * 5000 + ".js")
    assert status == 404
    assert json.loads(body)["error"]["code"] == "not_found"
    assert fetch(server, "GET", "/" + "/".join(["d"] * 500) + "/x.js")[0] == 404
    assert fetch(server, "GET", "/index.html")[0] == 200  # o servidor segue de pé


def test_the_api_stays_json_with_the_front_on_even_for_a_name_that_looks_like_a_file(server):
    status, headers, body = fetch(server, "GET", "/tables/abc/rules")
    assert status == 404  # mesa que não existe: erro da API, não "arquivo não encontrado"
    assert headers["Content-Type"].startswith("application/json")
    assert "Content-Security-Policy" not in headers
    assert "mesa" in json.loads(body)["error"]["message"]
    status, _, body = fetch(server, "GET", "/tables/abc/nada.js")
    assert (status, json.loads(body)["error"]["code"]) == (404, "not_found")


def test_one_keep_alive_connection_serves_files_and_api_back_to_back(server):
    conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
    try:
        seen = []
        for method, path in [
            ("GET", "/index.html"),
            ("HEAD", f"/{HASHED_JS}"),
            ("GET", "/campaigns"),
            ("GET", "/nao-existe.js"),
            ("GET", f"/{HASHED_JS}"),
            ("HEAD", "/index.html"),
            ("GET", "/"),
        ]:
            conn.request(method, path)
            response = conn.getresponse()
            body = response.read()  # esvazia: um HEAD com corpo desalinharia a próxima resposta
            seen.append((response.status, len(body)))
        assert [status for status, _ in seen] == [200, 200, 200, 404, 200, 200, 200]
        assert [size for _, size in seen][1] == 0
        assert [size for _, size in seen][5] == 0
        assert seen[0][1] == seen[6][1] > 0
    finally:
        conn.close()


def test_the_site_needs_an_existing_folder_with_an_index(tmp_path):
    with pytest.raises(StaticError, match="não existe"):
        StaticSite(tmp_path / "nada")
    (tmp_path / "vazia").mkdir()
    with pytest.raises(StaticError, match=r"não tem index\.html"):
        StaticSite(tmp_path / "vazia")


def test_the_web_flag_reaches_the_server_and_a_bad_folder_stops_the_start(
    tmp_path, web, monkeypatch, capsys
):
    seen = []
    monkeypatch.setattr(
        "devaneio.server.__main__.make_server",
        lambda host, port, _service, static=None: seen.append(static) or _FakeServer(host, port),
    )
    base = [
        "--campanhas",
        str(CAMPAIGN_PATH.parent),
        "--dados",
        str(tmp_path / "d"),
        "--porta",
        "0",
    ]
    assert main([*base, "--web", str(web)]) == 0
    assert isinstance(seen[0], StaticSite)
    assert seen[0].root == web.resolve()
    assert main([*base]) == 0
    assert seen[1] is None
    assert main([*base, "--web", str(tmp_path / "nada")]) == 1
    assert "não existe" in capsys.readouterr().err


class _FakeServer:
    def __init__(self, host, port):
        self.server_address = (host, port or 4242)

    def serve_forever(self):
        raise KeyboardInterrupt

    def server_close(self):
        pass
