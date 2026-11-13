import json
import subprocess
import sys
from pathlib import Path

import pytest

from devaneio.cli import CliError, CommandError, execute, load_game, new_game, save_game
from devaneio.engine import resolve_check
from devaneio.rules import CheckOutcome

from conftest import CAMPAIGN_PATH


@pytest.fixture
def session(tmp_path):
    return new_game(CAMPAIGN_PATH, tmp_path / "partida.json", seed=7)


def run(session, *lines):
    """Executa várias linhas; devolve a sessão final e o texto da última."""
    text = ""
    for line in lines:
        session, text = execute(session, line)
    return session, text


# --- partida em disco ---------------------------------------------------------


def test_new_game_writes_save_with_relative_campaign_path(session, tmp_path):
    data = json.loads((tmp_path / "partida.json").read_text(encoding="utf-8"))
    assert data["save_version"] == 1
    assert (tmp_path / data["campaign_path"]).resolve() == CAMPAIGN_PATH
    assert data["state"]["rng_seed"] == 7 and data["state"]["turn"] == 0
    assert session.rules.id == "default"


def test_random_seed_is_portable(tmp_path):
    session = new_game(CAMPAIGN_PATH, tmp_path / "p.json")
    assert 0 <= session.state.rng_seed < 2**53


def test_save_and_load_roundtrip(session):
    session, _ = run(session, 'entrar aria "Aria" FOR=3', "ir floresta", "fim")
    save_game(session)
    loaded = load_game(session.save_path)
    assert loaded.state == session.state
    assert loaded.campaign == session.campaign


def test_load_rejects_incoherent_save(session):
    data = json.loads(session.save_path.read_text(encoding="utf-8"))
    data["state"]["current_location_id"] = "limbo"
    session.save_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(CliError, match="current_location_id 'limbo'"):
        load_game(session.save_path)


def test_new_game_rejects_campaign_incompatible_with_rules(tmp_path):
    data = json.loads(CAMPAIGN_PATH.read_text(encoding="utf-8"))
    data["npcs"][0]["attributes"] = {"XIS": 1}
    bad = tmp_path / "ruim.json"
    bad.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(CliError, match="atributo 'XIS'"):
        new_game(bad, tmp_path / "p.json", seed=1)


# --- comandos -----------------------------------------------------------------


def test_look_at_start(session):
    _, text = run(session, "olhar")
    assert text.startswith("Turno 0 — Vila de Pedra Alta (vila)")
    assert "Saídas: Floresta Cinzenta (floresta)" in text
    assert "Aqui: Bram (ferreiro) hp 10/10" in text
    assert "Grupo: ninguém ainda" in text


def test_join_then_look_and_sheet(session):
    session, text = run(session, 'entrar aria "Aria Ventania" FOR=3 AGI=1')
    assert text == "Aria Ventania entra na aventura (FOR 3, AGI 1, MEN 2, PRE 2; hp 12)."
    _, look = run(session, "olhar")
    assert "Grupo: Aria Ventania (aria) hp 12/12 | FOR 3 AGI 1 MEN 2 PRE 2" in look
    _, sheet = run(session, "ficha")
    assert sheet == "Aria Ventania (aria)\nhp 12/12\nFOR 3, AGI 1, MEN 2, PRE 2\nInventário: vazio"


@pytest.mark.parametrize(
    "line, fragment",
    [
        ("entrar aria", "uso: entrar"),
        ('entrar aria "Aria" FOR', "atributo inválido 'FOR'"),
        ('entrar aria "Aria" FOR=x', "atributo inválido"),
        ('entrar aria "Aria" FOR=9', "FOR = 9 fora de"),
        ("ir", "uso: ir"),
        ("ir ruinas", "'vila' não conecta a 'ruinas'"),
        ("testar lutar normal", "nenhum personagem na partida"),
        ("dançar", "comando desconhecido 'dançar'"),
        ('entrar aria "Aria', "aspas desbalanceadas"),
        ("aria:", "prefixo sem comando"),
        ("ferir ninguem 3", "alvo 'ninguem' não está na partida"),
        ("ferir ferreiro x", "uso: ferir"),
        ("log x", "uso: log"),
    ],
)
def test_command_errors_do_not_change_state(session, line, fragment):
    before = session.state
    with pytest.raises(CommandError, match=fragment):
        execute(session, line)
    assert session.state == before


def test_empty_line_is_a_noop(session):
    same, text = execute(session, "   ")
    assert same is session and text == ""


def test_move_and_log(session):
    session, text = run(session, "ir floresta")
    assert text == "O grupo vai de Vila de Pedra Alta para Floresta Cinzenta."
    session, look = run(session, "olhar")
    assert look.startswith("Turno 0 — Floresta Cinzenta (floresta)") and "Aqui: ninguém" in look
    _, log = run(session, "log")
    assert log == "[t0] O grupo vai de Vila de Pedra Alta para Floresta Cinzenta."


def test_check_with_single_character_needs_no_prefix(session):
    session, text = run(session, 'entrar aria "Aria"', "testar furtividade dificil vantagem")
    assert text.startswith("Aria testa Furtividade (2d6 + AGI, Vantagem) contra Difícil 11:")
    assert session.state.rng_draws == 2


def test_prefix_selects_the_actor_when_several(session):
    session, _ = run(session, 'entrar aria "Aria"', 'entrar zed "Zed" MEN=5')
    with pytest.raises(CommandError, match="há vários personagens \\(aria, zed\\)"):
        execute(session, "testar saber facil")
    _, text = run(session, "zed: testar saber facil")
    assert text.startswith("Zed testa Saber (2d6 + MEN) contra Fácil 7:")
    _, sheet = run(session, "ficha zed")
    assert sheet.startswith("Zed (zed)")
    with pytest.raises(CommandError, match="personagem 'bob' não está na partida"):
        execute(session, "bob: testar saber facil")


def test_hurt_npc_and_character(session):
    session, text = run(session, 'entrar aria "Aria"', "ferir ferreiro 10 queda")
    assert text == "Bram sofre 10 de dano (queda), hp 10 → 0, fora de combate"
    assert session.state.npcs["ferreiro"].alive is False
    _, look = run(session, "olhar")
    assert "Bram (ferreiro) hp 0/10, fora de combate" in look
    _, text = run(session, "ferir aria 3")
    assert text == "Aria sofre 3 de dano (dano), hp 10 → 7"


def test_attack_hits_or_misses_according_to_the_check(tmp_path):
    seen = set()
    for seed in range(40):
        session = new_game(CAMPAIGN_PATH, tmp_path / f"p{seed}.json", seed=seed)
        session, _ = run(session, 'entrar aria "Aria" FOR=3', "ir floresta", "ir ruinas")
        predicted = resolve_check(
            session.state, session.rules,
            character_id="aria", skill_id="lutar", difficulty_id="normal",
        )
        after, text = run(session, "atacar espada sacerdote")
        hp = after.state.npcs["sacerdote"].hp
        if predicted.outcome in (CheckOutcome.SUCCESS, CheckOutcome.CRITICAL_SUCCESS):
            assert hp < 12 and "Aria ataca Irmão Vael com Espada" in text
            assert [e.kind for e in after.state.events[-2:]] == ["check", "damage"]
            seen.add("hit")
        else:
            assert hp == 12 and text.endswith("O ataque não acerta.")
            assert after.state.events[-1].kind == "check"
            seen.add("miss")
    assert seen == {"hit", "miss"}


def test_attack_uses_the_weapon_skill(session):
    session, text = run(session, 'entrar aria "Aria"', "atacar arco ferreiro")
    assert "Aria testa Atirar (2d6 + AGI) contra Normal 9" in text


@pytest.mark.parametrize(
    "line, fragment",
    [
        ("atacar canhao ferreiro", "arma 'canhao' não existe"),
        ("atacar espada aria", "atacar a si mesmo"),
        ("atacar espada ninguem", "alvo 'ninguem'"),
        ("atacar espada", "uso: atacar"),
    ],
)
def test_attack_errors(session, line, fragment):
    session, _ = run(session, 'entrar aria "Aria"')
    with pytest.raises(CommandError, match=fragment):
        execute(session, line)


def test_end_turn(session):
    session, text = run(session, "fim")
    assert text == "Fim do turno 0. Começa o turno 1."
    assert session.state.turn == 1


def test_help_lists_every_command(session):
    from devaneio.cli.commands import COMMANDS

    _, text = run(session, "ajuda")
    for name in COMMANDS:
        assert f"  {name}" in text


# --- ponta a ponta pelo processo ----------------------------------------------


def test_end_to_end_through_the_process(tmp_path):
    save = tmp_path / "partida.json"
    created = subprocess.run(
        [sys.executable, "-m", "devaneio.cli", "nova", str(CAMPAIGN_PATH), str(save), "--seed", "3"],
        check=True, capture_output=True, text=True,
    )
    assert "Partida criada: A Sombra do Vale (seed 3)" in created.stdout

    script = "\n".join(['entrar aria "Aria" FOR=3', "ir floresta", "pular", "fim", "log", "sair"]) + "\n"
    played = subprocess.run(
        [sys.executable, "-m", "devaneio.cli", "jogar", str(save)],
        input=script, check=True, capture_output=True, text=True,
    )
    out = played.stdout
    assert "A Sombra do Vale" in out and "Turno 0 — Vila de Pedra Alta" in out
    assert "Aria entra na aventura" in out
    assert "erro: comando desconhecido 'pular'" in out
    assert "Fim do turno 0. Começa o turno 1." in out

    data = json.loads(save.read_text(encoding="utf-8"))
    assert data["state"]["turn"] == 1 and data["state"]["current_location_id"] == "floresta"
    assert [e["kind"] for e in data["state"]["events"]] == ["character_joined", "move", "turn_end"]


def test_missing_save_file_is_a_clean_error(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "devaneio.cli", "jogar", str(tmp_path / "nada.json")],
        capture_output=True, text=True,
    )
    assert result.returncode == 1 and "arquivo não encontrado" in result.stderr
