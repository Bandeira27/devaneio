import json
import os
import subprocess
import sys

from conftest import CAMPAIGN_PATH
from fakes import FakeLlmServer

KEY = "chave-de-teste-123"
PROPOSAL = json.dumps(
    {"actions": [{"kind": "move", "to": "floresta"}], "say": "Seguindo pela trilha."}
)


def respond(body):
    """Proposta para o prompt do mestre; prosa para o do narrador."""
    system = body["messages"][0]["content"]
    if "APENAS com um objeto JSON" in system:
        return 200, PROPOSAL
    return 200, "A trilha se abre diante do grupo."


def make_save(tmp_path):
    save = tmp_path / "partida.json"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "devaneio.cli",
            "nova",
            str(CAMPAIGN_PATH),
            str(save),
            "--seed",
            "3",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return save


def play(save, stdin, env_extra, *flags):
    env = {**os.environ, **env_extra}
    return subprocess.run(
        [sys.executable, "-m", "devaneio.cli", "jogar", str(save), *flags],
        input=stdin,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def llm_env(server):
    return {
        "DEVANEIO_LLM_BASE_URL": server.base_url,
        "DEVANEIO_LLM_MODEL": "m-teste",
        "DEVANEIO_LLM_API_KEY": KEY,
    }


def test_free_text_end_to_end(tmp_path):
    save = make_save(tmp_path)
    with FakeLlmServer(respond) as server:
        result = play(save, 'entrar aria "Aria"\nvou até a floresta\nsair\n', llm_env(server))
    out = result.stdout
    assert result.returncode == 0, result.stderr
    assert "LLM ligado (m-teste em 127.0.0.1:" in out
    assert "enviado a esse servidor" in out
    assert "Mestre: Seguindo pela trilha." in out
    assert "(ações propostas: ir floresta)" in out
    assert "A trilha se abre diante do grupo." in out
    assert "  [O grupo vai de Vila de Pedra Alta para Floresta Cinzenta.]" in out

    data = json.loads(save.read_text(encoding="utf-8"))
    assert data["state"]["current_location_id"] == "floresta"
    assert [e["kind"] for e in data["state"]["events"]][-2:] == ["move", "beat_done"]
    # a chave só vai no cabeçalho da requisição: nunca para a saída nem para o arquivo
    assert KEY not in out
    assert KEY not in result.stderr
    assert KEY not in save.read_text(encoding="utf-8")
    assert {r["authorization"] for r in server.requests} == {f"Bearer {KEY}"}
    proposals = [
        r
        for r in server.requests
        if "APENAS com um objeto JSON" in r["json"]["messages"][0]["content"]
    ]
    assert len(proposals) == 1
    assert len(server.requests) == 3


def test_known_commands_never_reach_the_llm_for_interpretation(tmp_path):
    save = make_save(tmp_path)
    with FakeLlmServer(respond) as server:
        result = play(save, 'entrar aria "Aria"\nir floresta\nsair\n', llm_env(server))
    assert result.returncode == 0
    prompts = [r["json"]["messages"][0]["content"] for r in server.requests]
    assert not any("APENAS com um objeto JSON" in p for p in prompts)  # só narração
    assert len(server.requests) == 2  # entrar + ir, ambos narrados


def test_narration_failure_falls_back_to_the_grammar(tmp_path):
    save = make_save(tmp_path)

    def flaky(body):
        if "APENAS com um objeto JSON" in body["messages"][0]["content"]:
            return 200, PROPOSAL
        return 500, b"narrador fora do ar"

    with FakeLlmServer(flaky) as server:
        result = play(save, 'entrar aria "Aria"\nvou à floresta\nsair\n', llm_env(server))
    assert "narração por LLM indisponível" in result.stdout
    assert "HTTP 500" in result.stdout
    data = json.loads(save.read_text(encoding="utf-8"))
    assert data["state"]["current_location_id"] == "floresta"  # o jogo seguiu


def test_without_llm_free_text_is_an_unknown_command(tmp_path):
    save = make_save(tmp_path)
    result = play(save, "vou até a floresta\nsair\n", {})
    assert "erro: comando desconhecido 'vou'" in result.stdout
    assert "LLM ligado" not in result.stdout


def test_flag_disables_the_configured_llm(tmp_path):
    save = make_save(tmp_path)
    with FakeLlmServer(respond) as server:
        result = play(save, "vou até a floresta\nsair\n", llm_env(server), "--sem-llm")
    assert "erro: comando desconhecido" in result.stdout
    assert "LLM ligado" not in result.stdout
    assert server.requests == []


def test_malformed_config_is_a_clean_error(tmp_path):
    save = make_save(tmp_path)
    result = play(save, "sair\n", {"DEVANEIO_LLM_BASE_URL": "ftp://x", "DEVANEIO_LLM_MODEL": "m"})
    assert result.returncode == 1
    assert "DEVANEIO_LLM_BASE_URL inválida" in result.stderr
