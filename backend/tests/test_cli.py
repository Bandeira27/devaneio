"""Ponta a ponta pelo processo: ``python -m devaneio.cli``."""

import json
import subprocess
import sys

from conftest import CAMPAIGN_PATH


def test_end_to_end_through_the_process(tmp_path):
    save = tmp_path / "partida.json"
    created = subprocess.run(
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
    assert "Partida criada: A Sombra do Vale (seed 3)" in created.stdout

    script = (
        "\n".join(['entrar aria "Aria" FOR=3', "ir floresta", "pular", "fim", "log", "sair"]) + "\n"
    )
    played = subprocess.run(
        [sys.executable, "-m", "devaneio.cli", "jogar", str(save)],
        input=script,
        check=True,
        capture_output=True,
        text=True,
    )
    out = played.stdout
    assert "A Sombra do Vale" in out
    assert "Turno 0 — Vila de Pedra Alta" in out
    assert "Aria entra na aventura" in out
    assert "erro: comando desconhecido 'pular'" in out
    assert "  [Fim do turno 0]" in out
    assert "  [Diretor: tensão 0.00; nada a fazer.]" in out

    data = json.loads(save.read_text(encoding="utf-8"))
    assert data["state"]["turn"] == 1
    assert data["state"]["current_location_id"] == "floresta"
    assert [e["kind"] for e in data["state"]["events"]] == [
        "beat_activated",
        "character_joined",
        "move",
        "beat_done",
        "director",
        "turn_end",
    ]


def test_missing_save_file_is_a_clean_error(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "devaneio.cli", "jogar", str(tmp_path / "nada.json")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "arquivo não encontrado" in result.stderr


def test_end_to_end_output_is_narrated(tmp_path):
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
    played = subprocess.run(
        [sys.executable, "-m", "devaneio.cli", "jogar", str(save)],
        input="ir floresta\nsair\n",
        check=True,
        capture_output=True,
        text=True,
    )
    assert "  [O grupo vai de Vila de Pedra Alta para Floresta Cinzenta.]" in played.stdout
    assert "  [Marco concluído: Chegada à vila.]" in played.stdout
    prose = [
        line
        for line in played.stdout.split("\n")
        if "Floresta Cinzenta" in line and not line.startswith("  [")
    ]
    assert prose  # a linha narrada cita o destino


def test_end_to_end_banner_and_lock(tmp_path):
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
            "1",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    played = subprocess.run(
        [sys.executable, "-m", "devaneio.cli", "jogar", str(save)],
        input='entrar aria "Aria"\nferir aria 99\nir floresta\nsair\n',
        check=True,
        capture_output=True,
        text=True,
    )
    assert "*** DERROTA: todo o grupo caiu." in played.stdout
    assert "erro: a partida terminou" in played.stdout


def test_a_missing_authors_system_is_an_error_message_not_a_traceback(tmp_path):
    data = json.loads(CAMPAIGN_PATH.read_text(encoding="utf-8"))
    data["rules_id"] = "meu-sistema"
    campaign = tmp_path / "campanha.json"
    campaign.write_text(json.dumps(data), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "devaneio.cli", "nova", str(campaign), str(tmp_path / "p.json")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "'meu-sistema' não encontrado" in result.stderr
    assert "Traceback" not in result.stderr


def test_jogar_shows_the_content_warnings_on_stderr(tmp_path):
    data = json.loads(CAMPAIGN_PATH.read_text(encoding="utf-8"))
    data["narration_id"] = "meu"
    campaign = tmp_path / "campanha.json"
    campaign.write_text(json.dumps(data), encoding="utf-8")
    pack = tmp_path / "narracoes" / "meu.json"
    pack.parent.mkdir()
    pack.write_text(json.dumps({"id": "meu", "extends": "pt-br"}), encoding="utf-8")
    save = tmp_path / "partida.json"
    base = [sys.executable, "-m", "devaneio.cli"]
    subprocess.run([*base, "nova", str(campaign), str(save)], check=True, capture_output=True)
    changed = {"id": "meu", "extends": "pt-br", "rules": {"turn_end": ["Fim #turno#."]}}
    pack.write_text(json.dumps(changed), encoding="utf-8")
    result = subprocess.run(
        [*base, "jogar", str(save)], input="sair\n", capture_output=True, text=True, check=False
    )
    assert "aviso: O pacote de narração 'meu' mudou" in result.stderr
    assert "aviso" not in result.stdout
