import time

import pytest

from devaneio.llm import LlmConfig, LlmError, OpenAiCompatClient
from fakes import FakeLlmServer

MESSAGES = [{"role": "user", "content": "oi"}]


def client_for(server, **kw):
    return OpenAiCompatClient(LlmConfig(base_url=server.base_url, model="m-teste", **kw))


# --- configuração -------------------------------------------------------------


def test_config_from_env_requires_url_and_model():
    assert LlmConfig.from_env({}) is None
    assert LlmConfig.from_env({"DEVANEIO_LLM_BASE_URL": "http://x/v1"}) is None
    assert LlmConfig.from_env({"DEVANEIO_LLM_MODEL": "m"}) is None


def test_config_from_env_full_and_defaults():
    cfg = LlmConfig.from_env(
        {
            "DEVANEIO_LLM_BASE_URL": " http://localhost:11434/v1 ",
            "DEVANEIO_LLM_MODEL": "llama",
            "DEVANEIO_LLM_API_KEY": "segredo-123",
            "DEVANEIO_LLM_TIMEOUT": "12.5",
        }
    )
    assert (cfg.base_url, cfg.model, cfg.timeout, cfg.host) == (
        "http://localhost:11434/v1",
        "llama",
        12.5,
        "localhost:11434",
    )
    local = LlmConfig.from_env({"DEVANEIO_LLM_BASE_URL": "http://l/v1", "DEVANEIO_LLM_MODEL": "m"})
    assert local.api_key is None
    assert local.timeout == 60.0


def test_config_hides_the_key_in_repr():
    cfg = LlmConfig(base_url="http://x/v1", model="m", api_key="segredo-123")
    assert "segredo-123" not in repr(cfg)
    assert "segredo-123" not in str(cfg)


@pytest.mark.parametrize(
    ("env", "fragment"),
    [
        ({"DEVANEIO_LLM_BASE_URL": "ftp://x", "DEVANEIO_LLM_MODEL": "m"}, "inválida"),
        ({"DEVANEIO_LLM_BASE_URL": "localhost:1234", "DEVANEIO_LLM_MODEL": "m"}, "inválida"),
        (
            {
                "DEVANEIO_LLM_BASE_URL": "http://x",
                "DEVANEIO_LLM_MODEL": "m",
                "DEVANEIO_LLM_TIMEOUT": "abc",
            },
            "não é número",
        ),
        (
            {
                "DEVANEIO_LLM_BASE_URL": "http://x",
                "DEVANEIO_LLM_MODEL": "m",
                "DEVANEIO_LLM_TIMEOUT": "0",
            },
            "positivo",
        ),
    ],
)
def test_config_rejects_malformed_values(env, fragment):
    with pytest.raises(LlmError, match=fragment):
        LlmConfig.from_env(env)


# --- cliente ------------------------------------------------------------------


def test_complete_posts_chat_completions_and_returns_content():
    with FakeLlmServer(lambda _body: (200, "olá, aventureiro")) as server:
        out = client_for(server, api_key="k-1").complete(MESSAGES, temperature=0.3)
    assert out == "olá, aventureiro"
    request = server.requests[0]
    assert request["path"] == "/v1/chat/completions"
    assert request["authorization"] == "Bearer k-1"
    assert request["json"] == {"model": "m-teste", "messages": MESSAGES, "temperature": 0.3}


def test_no_authorization_header_without_a_key():
    with FakeLlmServer(lambda _body: (200, "ok")) as server:
        client_for(server).complete(MESSAGES)
    assert server.requests[0]["authorization"] is None


def test_json_mode_asks_for_json_object():
    with FakeLlmServer(lambda _body: (200, "{}")) as server:
        client_for(server).complete(MESSAGES, json_mode=True)
    assert server.requests[0]["json"]["response_format"] == {"type": "json_object"}


def test_json_mode_is_retried_without_the_field_when_the_server_refuses_it():
    def respond(body):
        return (
            (400, {"error": "response_format não suportado"})
            if "response_format" in body
            else (200, "{}")
        )

    with FakeLlmServer(respond) as server:
        out = client_for(server).complete(MESSAGES, json_mode=True)
    assert out == "{}"
    assert len(server.requests) == 2
    assert "response_format" not in server.requests[1]["json"]


def test_http_errors_become_llm_errors_with_status_and_detail():
    with (
        FakeLlmServer(lambda _body: (401, {"error": "chave invalida"})) as server,
        pytest.raises(LlmError, match=r"HTTP 401.*chave invalida"),
    ):
        client_for(server).complete(MESSAGES)
    with (
        FakeLlmServer(lambda _body: (500, b"falha interna")) as server,
        pytest.raises(LlmError, match="HTTP 500: falha interna"),
    ):
        client_for(server).complete(MESSAGES, json_mode=True)  # 500 não dispara o retry
    assert len(server.requests) == 1


@pytest.mark.parametrize(
    ("payload", "fragment"),
    [
        (b"isto nao e json", "fora do formato"),
        ({"choices": []}, "fora do formato"),
        ({"choices": [{"message": {"content": None}}]}, "resposta vazia"),
        ("   ", "resposta vazia"),
    ],
)
def test_malformed_or_empty_responses(payload, fragment):
    with (
        FakeLlmServer(lambda _body: (200, payload)) as server,
        pytest.raises(LlmError, match=fragment),
    ):
        client_for(server).complete(MESSAGES)


def test_connection_refused():
    with FakeLlmServer(lambda _body: (200, "x")) as server:
        dead = server.base_url
    with pytest.raises(LlmError, match="falha de conexão"):
        OpenAiCompatClient(LlmConfig(base_url=dead, model="m", timeout=2)).complete(MESSAGES)


def test_timeout():
    def slow(body):
        time.sleep(1.0)
        return 200, "tarde demais"

    with FakeLlmServer(slow) as server, pytest.raises(LlmError, match="falha de conexão"):
        client_for(server, timeout=0.3).complete(MESSAGES)
