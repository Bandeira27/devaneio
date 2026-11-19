"""Configuração do LLM da máquina: precedência, chave em arquivo à parte, rotas do editor e troca sem reiniciar."""

import contextlib
import http.client
import json
import os
import stat
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from conftest import CAMPAIGN_PATH
from devaneio.llm import LlmConfig
from devaneio.server import ApiFailure, Catalog, Storage, TableService
from devaneio.server import __main__ as entry
from devaneio.server.database import DB_NAME, Database, StorageBusy
from devaneio.server.editor import EditorService
from devaneio.server.files import prepare_data_dir
from devaneio.server.http import make_server
from devaneio.server.migrations import migrate
from devaneio.server.models import LlmSettingsUpdate
from devaneio.server.settings_store import KEY_FILE, SettingsStore
from fakes import FakeLlmServer

KEY = "sk-CANARIO-9f3a7c1d"  # chave de teste: o canário que nunca pode vazar
ENV = LlmConfig(
    base_url="http://ambiente.example/v1", model="m-ambiente", api_key="chave-do-ambiente"
)


@pytest.fixture
def data_dir(tmp_path):
    return prepare_data_dir(tmp_path / "dados")


@pytest.fixture
def db(data_dir):
    database = Database(data_dir / DB_NAME)
    migrate(database)
    yield database
    database.close()


def make_store(db, data_dir, **kw):
    return SettingsStore(db, data_dir, **kw)


def update(**over):
    body = {
        "base_url": "http://127.0.0.1:11434/v1",
        "model": "qwen3",
        "timeout": 30.0,
        "api_key": KEY,
    }
    body.update(over)
    return LlmSettingsUpdate.model_validate(body)


# --- precedência ----------------------------------------------------------------------


def test_without_anything_the_llm_is_off(db, data_dir):
    store = make_store(db, data_dir)
    assert store.effective() is None
    view = store.view()
    assert (view.source, view.key_set, view.description) == ("none", False, None)


def test_environment_is_the_fallback(db, data_dir):
    store = make_store(db, data_dir, environment=ENV)
    assert store.effective() == ENV
    assert store.view().source == "environment"
    assert store.view().base_url is None  # o que vem do ambiente não aparece como "salvo"


def test_screen_wins_over_environment_and_keeps_the_environment_key_out(db, data_dir):
    store = make_store(db, data_dir, environment=ENV)
    store.save(update(api_key=None))
    config = store.effective()
    assert (config.base_url, config.model, config.timeout) == (
        "http://127.0.0.1:11434/v1",
        "qwen3",
        30.0,
    )
    assert config.api_key is None  # a chave do ambiente nunca viaja para uma URL escolhida na tela
    assert store.view().source == "screen"


def test_screen_config_uses_the_key_file(db, data_dir):
    store = make_store(db, data_dir)
    store.save(update())
    assert store.effective().api_key == KEY
    assert store.view().key_set is True


def test_disabled_ignores_everything(db, data_dir):
    store = make_store(db, data_dir, environment=ENV, disabled=True)
    store.save(update())
    assert store.effective() is None
    assert store.view().disabled is True


def test_saving_without_a_key_keeps_the_current_one(db, data_dir):
    store = make_store(db, data_dir)
    store.save(update())
    store.save(update(model="outro-modelo", api_key=None))
    assert store.effective().model == "outro-modelo"
    assert store.effective().api_key == KEY


def test_clear_key_keeps_url_and_model(db, data_dir):
    store = make_store(db, data_dir)
    store.save(update())
    view = store.clear_key()
    assert view.key_set is False
    assert view.model == "qwen3"
    assert not (data_dir / KEY_FILE).exists()


def test_clear_goes_back_to_the_environment(db, data_dir):
    store = make_store(db, data_dir, environment=ENV)
    store.save(update())
    view = store.clear()
    assert (view.source, view.base_url, view.key_set) == ("environment", None, False)
    assert store.effective() == ENV


def test_a_new_store_on_the_same_files_sees_the_saved_config(db, data_dir):
    make_store(db, data_dir).save(update())
    again = make_store(db, data_dir)
    assert again.effective().api_key == KEY  # sobrevive a reiniciar o servidor


# --- validação ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        {"base_url": "ftp://x/v1"},
        {"base_url": "http://"},
        {"base_url": "http://usuario:senha@host/v1"},
        {"base_url": "http://host/v1?key=segredo"},
        {"base_url": "http://host/v1#ancora"},
        {"base_url": "http://host:abc/v1"},
        {"model": "   "},
        {"api_key": "tem espaco"},
        {"api_key": "quebra\nde-linha"},
    ],
)
def test_invalid_settings_are_refused_without_echoing_the_key(db, data_dir, bad):
    store = make_store(db, data_dir)
    with pytest.raises(ApiFailure) as caught:
        store.save(update(**bad))
    assert caught.value.status == 422
    assert KEY not in caught.value.message
    assert store.effective() is None  # nada foi guardado


# --- a chave: arquivo à parte, privado, sem vazar --------------------------------------


@pytest.mark.skipif(os.name != "posix", reason="modos POSIX")
def test_key_file_is_private_and_replaced_atomically(db, data_dir):
    store = make_store(db, data_dir)
    store.save(update())
    path = data_dir / KEY_FILE
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    store.save(update(api_key="outra-chave"))
    assert store.effective().api_key == "outra-chave"
    assert [p.name for p in data_dir.iterdir() if p.name.startswith(".llm")] == []  # sem temporário


@pytest.mark.skipif(os.name != "posix", reason="modos POSIX")
def test_loose_key_file_is_closed_when_read(db, data_dir, capsys):
    store = make_store(db, data_dir)
    store.save(update())
    (data_dir / KEY_FILE).chmod(0o644)
    store.view()
    assert stat.S_IMODE((data_dir / KEY_FILE).stat().st_mode) == 0o600
    assert KEY not in capsys.readouterr().err


def test_the_key_is_never_in_the_database_file_nor_in_the_view(db, data_dir):
    store = make_store(db, data_dir)
    view = store.save(update())
    assert KEY not in view.model_dump_json()
    assert "api_key" not in view.model_dump()
    db.close()
    for path in data_dir.iterdir():
        if path.name != KEY_FILE:
            assert KEY.encode() not in path.read_bytes(), path.name  # nem .db, nem -wal


def test_backup_of_the_database_does_not_carry_the_key(db, data_dir, tmp_path):
    make_store(db, data_dir).save(update())
    target = tmp_path / "copia.db"
    db.backup_to(target)
    assert KEY.encode() not in target.read_bytes()


# --- teste de conexão -----------------------------------------------------------------


def test_connection_test_ok_sends_the_key_only_in_the_header(db, data_dir):
    store = make_store(db, data_dir)
    with FakeLlmServer(lambda _body: (200, "ok")) as server:
        store.save(update(base_url=server.base_url))
        result = store.test()
    assert result.ok is True
    assert server.requests[0]["authorization"] == f"Bearer {KEY}"
    assert KEY not in json.dumps(server.requests[0]["json"])


def test_connection_test_without_config(db, data_dir):
    result = make_store(db, data_dir).test()
    assert (result.ok, result.message) == (False, "Não há LLM configurado.")


@pytest.mark.parametrize(
    ("status", "expected"),
    [(401, "recusou a chave (HTTP 401)"), (404, "(HTTP 404)"), (500, "erro (HTTP 500)")],
)
def test_connection_test_explains_http_failures_without_echoing_the_body(
    db, data_dir, status, expected
):
    store = make_store(db, data_dir)
    with FakeLlmServer(lambda _body: (status, {"error": "ECO-DO-SERVIDOR " + KEY})) as server:
        store.save(update(base_url=server.base_url))
        result = store.test()
    assert result.ok is False
    assert expected in result.message
    assert "ECO-DO-SERVIDOR" not in result.message
    assert KEY not in result.message


def test_connection_test_when_nobody_answers(db, data_dir):
    store = make_store(db, data_dir)
    store.save(update(base_url="http://127.0.0.1:1/v1", timeout=2.0))
    result = store.test()
    assert result.ok is False
    assert "127.0.0.1" not in result.message  # frase fixa, sem eco do endereço
    assert KEY not in result.message


def test_connection_test_with_an_answer_in_the_wrong_format(db, data_dir):
    store = make_store(db, data_dir)
    with FakeLlmServer(lambda _body: (200, {"nao": "e chat"})) as server:
        store.save(update(base_url=server.base_url))
        assert "formato" in store.test().message


# --- rotas do editor ------------------------------------------------------------------


class Api:
    def __init__(self, port):
        self.port = port

    def call(self, method, path, body=None, *, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        hdrs = {"Host": f"localhost:{self.port}", **(headers or {})}
        data = json.dumps(body).encode() if body is not None else None
        if data is not None:
            hdrs["Content-Type"] = "application/json"
        with contextlib.suppress(BrokenPipeError, ConnectionResetError):
            connection.request(method, path, body=data, headers=hdrs)
        response = connection.getresponse()
        raw = response.read()
        connection.close()
        return response.status, json.loads(raw or b"null"), raw


@pytest.fixture
def world(tmp_path, db, data_dir):
    root = tmp_path / "campanhas"
    root.mkdir()
    (root / "sombra-do-vale.json").write_text(
        CAMPAIGN_PATH.read_text(encoding="utf-8"), encoding="utf-8"
    )
    catalog = Catalog(root)
    storage = Storage(tmp_path / "mesas", max_tables=10)
    store = make_store(db, data_dir)
    service = TableService(catalog, storage, llm=store.effective)
    server = make_server("127.0.0.1", 0, service, None, EditorService(catalog, storage, store))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield Api(server.server_address[1]), service, store
    server.shutdown()
    server.server_close()


def test_llm_settings_round_trip_and_the_key_never_comes_back(world):
    api, _service, _store = world
    status, view, raw = api.call("GET", "/editor/settings/llm")
    assert (status, view["source"], view["key_set"]) == (200, "none", False)
    status, view, raw = api.call("PUT", "/editor/settings/llm", update().model_dump())
    assert status == 200
    assert (view["model"], view["key_set"], view["source"]) == ("qwen3", True, "screen")
    assert KEY.encode() not in raw
    status, view, raw = api.call("GET", "/editor/settings/llm")
    assert KEY.encode() not in raw
    assert "api_key" not in view


def test_saving_in_the_screen_turns_the_llm_on_without_restarting(world):
    api, service, _store = world
    assert service.llm is None
    api.call("PUT", "/editor/settings/llm", update().model_dump())
    assert service.llm is not None
    assert service.llm.model == "qwen3"
    api.call("DELETE", "/editor/settings/llm")
    assert service.llm is None


def test_invalid_url_is_422_and_does_not_echo_the_key(world):
    api, _service, _store = world
    status, body, raw = api.call(
        "PUT", "/editor/settings/llm", update(base_url="http://u:s@host/v1").model_dump()
    )
    assert status == 422
    assert body["error"]["code"] == "invalid_settings"
    assert KEY.encode() not in raw


def test_delete_key_route(world):
    api, _service, store = world
    api.call("PUT", "/editor/settings/llm", update().model_dump())
    status, view, _ = api.call("DELETE", "/editor/settings/llm/key")
    assert (status, view["key_set"], view["model"]) == (200, False, "qwen3")
    assert store.effective().api_key is None


def test_test_route(world):
    api, _service, _store = world
    with FakeLlmServer(lambda _body: (200, "ok")) as server:
        api.call("PUT", "/editor/settings/llm", update(base_url=server.base_url).model_dump())
        status, result, _ = api.call("POST", "/editor/settings/llm/test")
    assert (status, result["ok"]) == (200, True)


def test_settings_routes_share_the_editor_guard(world):
    api, _service, _store = world
    body = update().model_dump()
    assert api.call("GET", "/editor/settings/llm", headers={"Host": "evil.example"})[0] == 403
    assert (
        api.call("PUT", "/editor/settings/llm", body, headers={"Origin": "http://evil.example"})[0]
        == 403
    )
    assert api.call("GET", "/editor/settings/llm", headers={"X-Forwarded-For": "1.2.3.4"})[0] == 404
    assert api.call("GET", "/editor/settings/llm")[1]["source"] == "none"  # nada foi gravado


def test_settings_routes_are_404_without_a_store(tmp_path):
    root = tmp_path / "campanhas"
    root.mkdir()
    (root / "sombra-do-vale.json").write_text(
        CAMPAIGN_PATH.read_text(encoding="utf-8"), encoding="utf-8"
    )
    catalog = Catalog(root)
    storage = Storage(tmp_path / "mesas", max_tables=10)
    server = make_server(
        "127.0.0.1", 0, TableService(catalog, storage), None, EditorService(catalog, storage)
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    api = Api(server.server_address[1])
    assert api.call("GET", "/editor/settings/llm")[0] == 404
    server.shutdown()
    server.server_close()


def test_the_key_is_never_printed_by_the_server(world, capfd):
    api, _service, _store = world
    api.call("PUT", "/editor/settings/llm", update().model_dump())
    api.call("PUT", "/editor/settings/llm", update(base_url="http://u:s@h/v1").model_dump())
    api.call("DELETE", "/editor/settings/llm/key")
    captured = capfd.readouterr()
    assert KEY not in captured.out
    assert KEY not in captured.err


# --- achados da revisão ---------------------------------------------------------------


def test_changing_the_server_without_retyping_the_key_is_refused(db, data_dir):
    store = make_store(db, data_dir)
    store.save(update())
    with pytest.raises(ApiFailure) as caught:
        store.save(update(base_url="https://outro.example/v1", api_key=None))
    assert caught.value.status == 422
    assert "chave" in caught.value.message
    assert store.effective().base_url == "http://127.0.0.1:11434/v1"  # nada mudou
    # Com a chave de novo, ou depois de apagá-la, o servidor novo é aceito.
    store.save(update(base_url="https://outro.example/v1", api_key="nova-chave"))
    assert store.effective().api_key == "nova-chave"
    store.clear_key()
    store.save(update(base_url="https://terceiro.example/v1", api_key=None))
    assert store.effective().base_url == "https://terceiro.example/v1"


def test_changing_only_the_model_or_the_path_keeps_the_key(db, data_dir):
    store = make_store(db, data_dir)
    store.save(update())
    store.save(update(base_url="http://127.0.0.1:11434/outro/caminho", api_key=None))
    assert store.effective().api_key == KEY


@pytest.mark.parametrize("key", ["abc中def", "açaí", "com\x7fdel"])
def test_key_must_be_printable_ascii(db, data_dir, key):
    with pytest.raises(ApiFailure) as caught:
        make_store(db, data_dir).save(update(api_key=key))
    assert caught.value.status == 422
    assert key not in caught.value.message


def test_a_database_failure_leaves_key_and_cache_untouched(db, data_dir, monkeypatch):
    store = make_store(db, data_dir)
    store.save(update())
    assert store.effective().api_key == KEY  # esquenta o cache

    def busy(_work):
        raise StorageBusy()

    monkeypatch.setattr(db, "write", busy)
    with pytest.raises(StorageBusy):
        store.save(update(model="novo", api_key="chave-nova"))
    monkeypatch.undo()
    assert store.effective().model == "qwen3"
    assert store.effective().api_key == KEY  # a chave só é trocada depois do banco


def test_clear_failing_on_the_key_file_is_a_clean_error_and_drops_the_cache(
    db, data_dir, monkeypatch
):
    store = make_store(db, data_dir)
    store.save(update())
    assert store.effective() is not None
    real_unlink = type(data_dir).unlink

    def deny(self, *args, **kwargs):
        if self.name == KEY_FILE:
            raise PermissionError("sem permissão")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(type(data_dir), "unlink", deny)
    with pytest.raises(ApiFailure) as caught:
        store.clear()
    assert caught.value.status == 500
    assert "sem permissão" not in caught.value.message
    monkeypatch.undo()
    assert store.effective() is None  # o banco foi limpo e o cache não ficou velho
    assert (data_dir / KEY_FILE).exists()  # a chave seguiu no disco, e a tela ainda a mostra


def test_a_slow_database_read_does_not_hold_the_store_lock(db, data_dir):
    store = make_store(db, data_dir)
    inside, release = threading.Event(), threading.Event()
    real = store._read_screen

    def slow():
        inside.set()
        release.wait(5)
        return real()

    store._read_screen = slow
    first = threading.Thread(target=store.effective)
    first.start()
    assert inside.wait(5)
    # Outro pedido que só precisa da trava (invalidar) não fica preso atrás da leitura lenta.
    done = threading.Event()
    threading.Thread(target=lambda: (store.clear_key(), done.set())).start()
    release.set()
    first.join(5)
    assert done.wait(5)


def test_a_result_computed_before_a_change_is_not_cached(db, data_dir):
    store = make_store(db, data_dir)
    store.save(update(model="velho", api_key=None))
    real = store._read_screen
    gate = threading.Event()
    stale = []

    def read_then_wait():
        value = real()
        stale.append(value)
        gate.wait(5)
        return value

    store._cached = None  # começa sem cache, para o cálculo ir ao banco
    store._read_screen = read_then_wait
    worker = threading.Thread(target=store.effective)
    worker.start()
    deadline = time.monotonic() + 5
    while not stale and time.monotonic() < deadline:
        time.sleep(0.01)
    assert stale
    store._read_screen = real
    store.save(update(model="novo", api_key=None))  # muda enquanto o outro calcula
    gate.set()
    worker.join(5)
    assert store.effective().model == "novo"


def test_a_redirect_is_not_followed_so_the_key_does_not_travel(db, data_dir):
    seen = []

    class Target(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append(self.headers.get("Authorization"))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    target = ThreadingHTTPServer(("127.0.0.1", 0), Target)
    threading.Thread(target=target.serve_forever, daemon=True).start()

    class Redirector(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{target.server_address[1]}/x")
            self.end_headers()

        def log_message(self, *args):
            pass

    redirector = ThreadingHTTPServer(("127.0.0.1", 0), Redirector)
    threading.Thread(target=redirector.serve_forever, daemon=True).start()
    store = make_store(db, data_dir)
    store.save(update(base_url=f"http://127.0.0.1:{redirector.server_address[1]}/v1"))
    result = store.test()
    target.shutdown()
    redirector.shutdown()
    target.server_close()
    redirector.server_close()
    assert result.ok is False
    assert "HTTP 302" in result.message
    assert seen == []  # o destino do redirect nunca foi chamado, com ou sem chave


def test_sem_llm_does_not_even_read_an_invalid_environment(tmp_path, monkeypatch, capsys):
    root = tmp_path / "campanhas"
    root.mkdir()
    (root / "sombra-do-vale.json").write_text(
        CAMPAIGN_PATH.read_text(encoding="utf-8"), encoding="utf-8"
    )

    class Quiet:
        server_address = ("127.0.0.1", 0)

        def serve_forever(self):
            raise KeyboardInterrupt

        def server_close(self):
            pass

    monkeypatch.setattr(entry, "make_server", lambda *_args, **_kwargs: Quiet())
    monkeypatch.setenv("DEVANEIO_LLM_BASE_URL", "lixo")
    monkeypatch.setenv("DEVANEIO_LLM_MODEL", "m")
    args = [
        "--campanhas",
        str(root),
        "--dados",
        str(tmp_path / "d"),
        "--sem-navegador",
        "--porta",
        "0",
    ]
    assert entry.main([*args, "--sem-llm"]) == 0
    assert entry.main(args) == 1  # sem a opção, o ambiente inválido continua sendo erro
    assert "DEVANEIO_LLM_BASE_URL inválida" in capsys.readouterr().err
