import json
from dataclasses import replace

import pytest

from conftest import CAMPAIGN_PATH
from devaneio.engine import resolve_check
from devaneio.game import (
    COMMANDS,
    CommandError,
    GameError,
    GameOverError,
    TableMeta,
    connect_llm,
    execute,
    format_output,
    is_command,
    load_game,
    narrate_batch,
    new_game,
    save_game,
    status_banner,
)
from devaneio.game.commands import parse_line, split_actor
from devaneio.llm import LlmConfig, LlmError
from devaneio.rules import CheckOutcome
from fakes import ScriptedClient


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
    assert data["state"]["rng_seed"] == 7
    assert data["state"]["turn"] == 0
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
    with pytest.raises(GameError, match="current_location_id 'limbo'"):
        load_game(session.save_path)


def test_new_game_rejects_campaign_incompatible_with_rules(tmp_path):
    data = json.loads(CAMPAIGN_PATH.read_text(encoding="utf-8"))
    data["npcs"][0]["attributes"] = {"XIS": 1}
    bad = tmp_path / "ruim.json"
    bad.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(GameError, match="atributo 'XIS'"):
        new_game(bad, tmp_path / "p.json", seed=1)


def test_save_is_atomic_and_leaves_no_temp_file(session, monkeypatch):
    session, _ = run(session, 'entrar aria "Aria"')
    before = session.save_path.read_text(encoding="utf-8")

    def fail(_src, _dst):
        raise OSError("disco cheio")

    monkeypatch.setattr("devaneio.game.session.os.replace", fail)
    with pytest.raises(OSError, match="disco cheio"):
        save_game(session)
    assert session.save_path.read_text(encoding="utf-8") == before
    assert list(session.save_path.parent.glob(".partida-*")) == []
    monkeypatch.undo()
    save_game(session)
    assert list(session.save_path.parent.glob(".partida-*")) == []
    assert load_game(session.save_path).state == session.state


def test_table_is_preserved_by_a_solo_session(session):
    table = TableMeta.model_validate(
        {
            "invite_hash": "abc",
            "players": {"p1": {"name": "Ana", "role": "host", "token_hash": "h"}},
            "acted": {"aria": 0},
        }
    )
    save_game(replace(session, table=table))
    loaded = load_game(session.save_path)
    assert loaded.table == table
    loaded, _ = run(loaded, 'entrar aria "Aria"', "ir floresta")
    save_game(loaded)
    data = json.loads(session.save_path.read_text(encoding="utf-8"))
    assert data["table"]["players"]["p1"]["name"] == "Ana"
    assert data["table"]["acted"] == {"aria": 0}
    assert load_game(session.save_path).table == table


def test_save_without_table_writes_null(session):
    data = json.loads(session.save_path.read_text(encoding="utf-8"))
    assert data["table"] is None


def test_campaign_root_restricts_where_the_campaign_may_live(session, tmp_path):
    assert load_game(session.save_path, campaign_root=CAMPAIGN_PATH.parent).campaign.id == (
        session.campaign.id
    )
    with pytest.raises(GameError, match="fora da pasta permitida"):
        load_game(session.save_path, campaign_root=tmp_path)
    data = json.loads(session.save_path.read_text(encoding="utf-8"))
    data["campaign_path"] = "../../" + data["campaign_path"]
    session.save_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(GameError, match="fora da pasta permitida"):
        load_game(session.save_path, campaign_root=tmp_path)


# --- comandos -----------------------------------------------------------------


def test_look_at_start(session):
    _, text = run(session, "olhar")
    assert text.startswith("Turno 0 — Vila de Pedra Alta (vila)")
    assert "Saídas: Floresta Cinzenta (floresta)" in text
    assert "Aqui: Bram (ferreiro) hp 10/10\n" in text
    assert "Marcos ativos: Chegada à vila" in text
    assert "Grupo: ninguém ainda" in text


def test_new_game_starts_with_root_beats_active(session):
    assert session.state.beats["chegada"].value == "active"
    assert session.state.events[0].kind == "beat_activated"


def test_beats_advance_after_player_actions(session):
    session, text = run(session, 'entrar aria "Aria"', "ir floresta")
    assert (
        text == "O grupo vai de Vila de Pedra Alta para Floresta Cinzenta."
    )  # sem persuadir, nada fecha
    session, text = run(session, "marco concluir chegada", "ir ruinas")
    assert text.endswith("\nMarco ativado: A pista nas ruínas.")
    _, look = run(session, "olhar")
    assert "Irmão Vael (sacerdote) hp 12/12, hostil" in look
    _, beats = run(session, "marcos")
    assert beats == (
        "[concluído] Chegada à vila (chegada)\n"
        "[ativo] A pista nas ruínas (pista) (exige: chegada)\n"
        "[pendente] Confronto com o culto (confronto) (exige: pista)"
    )


def test_manual_beat_commands(session):
    session, text = run(
        session,
        'entrar aria "Aria"',
        "ir floresta",
        "marco concluir chegada",
        "ir ruinas",
        "marco concluir pista",
    )
    assert text == "Marco concluído: A pista nas ruínas.\nMarco ativado: Confronto com o culto."
    with pytest.raises(CommandError, match="está 'active', precisava estar 'pending'"):
        execute(session, "marco ativar confronto")
    with pytest.raises(CommandError, match="uso: marco"):
        execute(session, "marco pular pista")


def test_end_turn_runs_the_director(session):
    session, text = run(session, 'entrar aria "Aria"', "ir floresta", "ir ruinas", "fim")
    assert "Irmão Vael testa Lutar (2d6 + FOR) contra Normal 9:" in text
    assert "Diretor: tensão" in text
    assert text.endswith("Fim do turno 0. Começa o turno 1.")
    assert session.state.turn == 1
    kinds = [e.kind for e in session.state.events]
    assert kinds[-2:] == ["director", "turn_end"]
    assert "check" in kinds


def test_join_then_look_and_sheet(session):
    session, text = run(session, 'entrar aria "Aria Ventania" FOR=3 AGI=1')
    assert text == "Aria Ventania entra na aventura (FOR 3, AGI 1, MEN 2, PRE 2; hp 12)."
    _, look = run(session, "olhar")
    assert "Grupo: Aria Ventania (aria) hp 12/12 | FOR 3 AGI 1 MEN 2 PRE 2" in look
    _, sheet = run(session, "ficha")
    assert sheet == "Aria Ventania (aria)\nhp 12/12\nFOR 3, AGI 1, MEN 2, PRE 2\nInventário: vazio"


@pytest.mark.parametrize(
    ("line", "fragment"),
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
    assert same is session
    assert text == ""


@pytest.mark.parametrize(
    ("line", "actor", "rest"),
    [
        ("aria: testar lutar normal", "aria", "testar lutar normal"),
        ("  aria:   testar lutar  ", "aria", "testar lutar"),
        ("aria:\ttestar lutar", "aria", "testar lutar"),
        ("testar lutar normal", None, "testar lutar normal"),
        ("'aria:' testar lutar", None, "'aria:' testar lutar"),
        ("aria:", "aria", ""),
        (":", None, ":"),
        ("digo: olá, Bram", "digo", "olá, Bram"),
    ],
)
def test_split_actor_takes_only_a_bare_first_word(line, actor, rest):
    assert split_actor(line) == (actor, rest)


def test_parse_line_lowercases_the_command_and_keeps_quoted_args():
    assert parse_line('aria: ENTRAR aria "Aria Luz" FOR=3') == (
        "aria",
        "entrar",
        ["aria", "Aria Luz", "FOR=3"],
    )
    assert parse_line("olhar") == (None, "olhar", [])
    with pytest.raises(CommandError, match="linha vazia"):
        parse_line("   ")
    with pytest.raises(CommandError, match="prefixo sem comando"):
        parse_line("aria:")


def test_quoted_prefix_is_not_an_actor(session):
    session, _ = run(session, 'entrar aria "Aria"')
    with pytest.raises(CommandError, match="comando desconhecido 'aria:'"):
        execute(session, "'aria:' testar lutar normal")


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("olhar", True),
        ("aria: Testar lutar normal", True),
        ('aria: entrar x "aspas soltas', True),
        ("tento convencer o ferreiro", False),
        ("bram: olá", False),
        ("", False),
        ("aria:", False),
    ],
)
def test_is_command_uses_the_same_prefix_rule(line, expected):
    assert is_command(line) is expected


def test_move_and_log(session):
    session, text = run(session, "ir floresta")
    assert text == "O grupo vai de Vila de Pedra Alta para Floresta Cinzenta."
    session, look = run(session, "olhar")
    assert look.startswith("Turno 0 — Floresta Cinzenta (floresta)")
    assert "Aqui: ninguém" in look
    session, _ = run(session, "marco concluir chegada")
    _, log = run(session, "log 2")
    assert log == (
        "[t0] O grupo vai de Vila de Pedra Alta para Floresta Cinzenta.\n"
        "[t0] Marco concluído: Chegada à vila."
    )


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
        session, _ = run(session, 'entrar aria "Aria" FOR=3 +espada', "ir floresta", "ir ruinas")
        predicted = resolve_check(
            session.state,
            session.rules,
            character_id="aria",
            skill_id="lutar",
            difficulty_id="normal",
        )
        after, text = run(session, "atacar espada sacerdote")
        hp = after.state.npcs["sacerdote"].hp
        if predicted.outcome in (CheckOutcome.SUCCESS, CheckOutcome.CRITICAL_SUCCESS):
            assert hp < 12
            assert "Aria ataca Irmão Vael com Espada" in text
            assert [e.kind for e in after.state.events[-2:]] == ["check", "damage"]
            seen.add("hit")
        else:
            assert hp == 12
            assert text.endswith("O ataque não acerta.")
            assert after.state.events[-1].kind == "check"
            seen.add("miss")
    assert seen == {"hit", "miss"}


def test_attack_uses_the_weapon_skill(session):
    session, text = run(session, 'entrar aria "Aria" +arco', "atacar arco ferreiro")
    assert "Aria testa Atirar (2d6 + AGI) contra Normal 9" in text


def test_attack_difficulty_comes_from_rules(session):
    session.rules.combat.attack_difficulty = "heroica"
    session, text = run(session, 'entrar aria "Aria" +espada', "atacar espada ferreiro")
    assert "contra Heroica 13" in text


@pytest.mark.parametrize(
    ("line", "fragment"),
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


def test_end_turn_without_hostiles(session):
    session, text = run(session, "fim")
    assert text == "Diretor: tensão 0.00; nada a fazer.\nFim do turno 0. Começa o turno 1."
    assert session.state.turn == 1


def test_help_lists_every_command(session):
    _, text = run(session, "ajuda")
    for name in COMMANDS:
        assert f"  {name}" in text


# --- narração na saída ----------------------------------------------------------


def test_format_output_narrates_new_events_with_mechanical_line(session):
    before = session.state
    after, text = run(session, 'entrar aria "Aria" FOR=3')
    out = format_output(session.narrator, before, after.state, text)
    lines = out.split("\n")
    assert len(lines) == 2
    assert "Aria" in lines[0]
    assert lines[0] != text
    assert lines[1] == "  [Aria entra na aventura (FOR 3, AGI 1, MEN 2, PRE 2; hp 12).]".replace(
        "AGI 1", "AGI 2"
    )


def test_format_output_keeps_plain_text_when_nothing_happened(session):
    _, text = run(session, "olhar")
    assert format_output(session.narrator, session.state, session.state, text) == text


# --- inventário, cura, descanso, desfecho ---------------------------------------


def test_join_with_items_and_sheet(session):
    session, _ = run(session, 'entrar aria "Aria" FOR=3 +espada +arco')
    assert session.state.characters["aria"].inventory == ["espada", "arco"]
    _, sheet = run(session, "ficha")
    assert sheet.endswith("Inventário: espada, arco")
    with pytest.raises(CommandError, match="item vazio"):
        execute(session, 'entrar zed "Zed" +')


def test_attack_requires_the_weapon_in_the_inventory(session):
    session, _ = run(session, 'entrar aria "Aria" +espada')
    with pytest.raises(
        CommandError, match="Aria não tem 'arco' no inventário \\(sempre disponível: punhos\\)"
    ):
        execute(session, "atacar arco ferreiro")
    _, text = run(session, "atacar espada ferreiro")
    assert "Aria testa Lutar" in text
    _, text = run(session, "atacar punhos ferreiro")  # arma padrão sempre disponível
    assert "Aria testa Lutar" in text


def test_heal_command(session):
    session, _ = run(session, 'entrar aria "Aria"', "ferir aria 6 queda")
    session, text = run(session, "curar aria 4 poção")
    assert text == "Aria recupera 4 de vida (poção), hp 4 → 8"
    with pytest.raises(CommandError, match="uso: curar"):
        execute(session, "curar aria")
    with pytest.raises(CommandError, match="precisa ser positiva"):
        execute(session, "curar aria 0")


def test_rest_command_heals_and_spends_the_turn(session):
    session, _ = run(session, 'entrar aria "Aria"', "ferir aria 6")
    session, text = run(session, "descansar")
    assert text.startswith("O grupo descansa: Aria +")
    assert "Fim do turno 0" in text
    assert session.state.turn == 1
    assert session.state.characters["aria"].hp > 4
    kinds = [e.kind for e in session.state.events]
    assert kinds[-3:] == ["rest", "director", "turn_end"]
    with pytest.raises(CommandError, match="uso: descansar"):
        execute(session, "descansar agora")


def test_rest_refused_when_nobody_is_hurt(session):
    session, _ = run(session, 'entrar aria "Aria"')
    with pytest.raises(CommandError, match="todos já estão com o hp máximo"):
        execute(session, "descansar")


def test_rest_refused_with_a_hostile_present(session):
    session, _ = run(session, 'entrar aria "Aria"', "ir floresta", "ir ruinas", "ferir aria 3")
    with pytest.raises(CommandError, match="Irmão Vael hostil por perto"):
        execute(session, "descansar")


def test_defeat_locks_actions_and_olhar_says_so(session):
    before = session.state
    session, _ = run(session, 'entrar aria "Aria"', "ferir aria 99")
    assert "DERROTA" in status_banner(before, session.state)
    assert status_banner(session.state, session.state) == ""
    with pytest.raises(GameOverError, match="a partida terminou \\(derrota: todo o grupo caiu\\)"):
        execute(session, "ir floresta")
    with pytest.raises(GameOverError) as info:
        execute(session, "fim")
    assert info.value.status.value == "lost"
    for allowed in ("olhar", "ficha", "marcos", "log", "ajuda"):
        run(session, allowed)
    _, look = run(session, "olhar")
    assert "Partida encerrada — derrota: todo o grupo caiu." in look


def test_victory_when_the_last_beat_closes(session):
    session, _ = run(
        session,
        'entrar aria "Aria" +espada',
        "ir floresta",
        "marco concluir chegada",
        "ir ruinas",
        "marco concluir pista",
    )
    before = session.state
    session, _ = run(session, "ferir sacerdote 99")
    assert all(s.value == "done" for s in session.state.beats.values())
    assert "VITÓRIA" in status_banner(before, session.state)
    with pytest.raises(CommandError, match="vitória"):
        execute(session, "fim")


def test_help_mentions_the_new_commands(session):
    _, text = run(session, "ajuda")
    for fragment in ("curar <alvo>", "descansar", "+item"):
        assert fragment in text


# --- personagem fora de combate -----------------------------------------------------


def with_fallen_allowed(session):
    combat = session.rules.combat.model_copy(update={"fallen_can_act": True})
    return replace(session, rules=session.rules.model_copy(update={"combat": combat}))


@pytest.fixture
def downed(session):
    session, _ = run(session, 'entrar aria "Aria"', 'entrar zed "Zed"', "ferir aria 99")
    return session


@pytest.mark.parametrize(
    "line",
    ["aria: testar lutar normal", "aria: atacar punhos ferreiro", "aria: ir floresta"],
)
def test_a_fallen_character_cannot_act(downed, line):
    before = downed.state
    with pytest.raises(CommandError, match="Aria está fora de combate e não pode agir"):
        execute(downed, line)
    assert downed.state == before


def test_the_others_still_act_and_the_group_still_moves(downed):
    _, text = run(downed, "zed: testar lutar normal")
    assert "Zed" in text
    _, moved = run(downed, "zed: ir floresta")
    assert "Floresta Cinzenta" in moved


def test_healing_gets_a_fallen_character_back_on_her_feet(downed):
    session, _ = run(downed, "curar aria 5")
    _, text = run(session, "aria: testar lutar normal")
    assert "Aria" in text


def test_the_rules_may_let_the_fallen_act(downed):
    _, text = run(with_fallen_allowed(downed), "aria: testar lutar normal")
    assert "Aria" in text
    _, moved = run(with_fallen_allowed(downed), "aria: ir floresta")
    assert "Floresta Cinzenta" in moved


def test_the_default_rules_say_the_fallen_cannot_act(session):
    assert session.rules.combat.fallen_can_act is False


# --- LLM: cliente e narração do lote ------------------------------------------------


def test_narrate_batch_returns_the_paragraph_or_the_fallback_note(session):
    state = session.state
    ok = ScriptedClient("A trilha se abre.")
    assert narrate_batch(ok, session.campaign, state, ["Fim do turno 0"]) == (
        "A trilha se abre.",
        "",
    )
    broken = ScriptedClient(LlmError("rede caiu"))
    paragraph, note = narrate_batch(broken, session.campaign, state, ["Fim do turno 0"])
    assert paragraph is None
    assert note == "(narração por LLM indisponível: rede caiu; usei a gramática)"


def test_connect_llm_builds_the_client_for_a_config():
    client = connect_llm(LlmConfig(base_url="http://localhost:11434/v1", model="qwen3"))
    assert client.description == "qwen3 em localhost:11434"
