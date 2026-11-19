"""Importar as partidas de mesa em JSON (as de antes do banco) para o banco, sem tocar nos arquivos originais."""

import json
import os
import shutil
from dataclasses import replace

import pytest

from conftest import CAMPAIGN_PATH, make_storage
from devaneio.game import SaveFile, TableMeta, build_save, new_game, save_game
from devaneio.game.table import Player
from devaneio.server import Catalog, TableService
from devaneio.server import __main__ as entry
from devaneio.server.__main__ import main
from devaneio.server.auth import hash_secret
from devaneio.server.cli_tools import import_main
from devaneio.server.database import DB_NAME, acquire_instance_lock
from devaneio.server.files import prepare_data_dir
from devaneio.server.models import CommandRequest, CreateTableRequest, JoinRequest
from devaneio.server.records import TableRecords
from devaneio.server.transfer import find_saves, import_saves

ID = "0123456789abcdef"
OTHER = "fedcba9876543210"
TOKEN = "token-do-anfitriao"  # noqa: S105 — texto de teste, não é senha


def old_save(folder, table_id=ID, *, with_table=True, **table_over):
    """Uma partida de mesa no formato antigo: o arquivo que o servidor guardava antes do banco."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{table_id}.json"
    session = new_game(CAMPAIGN_PATH, path, seed=7, start=False)
    if with_table:
        host = Player(name="Ana", role="host", token_hash=hash_secret(TOKEN))
        table = TableMeta(
            invite_hash=hash_secret("convite"), players={"p1": host}, phase="lobby", **table_over
        )
        save_game(replace(session, table=table))
    return path


@pytest.fixture
def world(tmp_path):
    catalog = Catalog(CAMPAIGN_PATH.parent)
    storage = make_storage(tmp_path / "dados", max_tables=10)
    return catalog, storage, tmp_path / "antigas"


def test_imports_a_table_keeping_id_tokens_invite_and_state(world):
    catalog, storage, folder = world
    original = old_save(folder)
    report = import_saves(storage, catalog, [folder])
    assert (report.imported, report.skipped, report.refused) == ([ID], [], [])
    session = TableRecords(storage, catalog).load(ID)
    data = SaveFile.model_validate_json(original.read_text(encoding="utf-8"))
    assert session.state == data.state
    assert session.table == data.table  # id, hashes do token e do convite, fase, jogadores
    assert storage.read(ID).campaign_path == "sombra-do-vale.json"  # relativo à pasta de campanhas


def test_a_second_import_adds_nothing(world):
    catalog, storage, folder = world
    old_save(folder)
    import_saves(storage, catalog, [folder])
    report = import_saves(storage, catalog, [folder])
    assert (report.imported, report.skipped) == ([], [ID])
    assert storage.count() == 1


def test_the_original_files_are_never_touched(world):
    catalog, storage, folder = world
    path = old_save(folder)
    before = (path.read_bytes(), path.stat().st_mtime_ns)
    import_saves(storage, catalog, [folder])
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before
    assert sorted(p.name for p in folder.iterdir()) == [f"{ID}.json"]


def test_the_file_date_becomes_the_last_update(world):
    catalog, storage, folder = world
    path = old_save(folder)
    os.utime(path, (1_700_000_000, 1_700_000_000))
    import_saves(storage, catalog, [path])
    [summary] = storage.summaries("sombra-do-vale.json")
    assert summary.updated_at == 1_700_000_000.0


def test_a_single_file_or_a_folder_both_work(world):
    catalog, storage, folder = world
    a, b = old_save(folder, ID), old_save(folder, OTHER)
    assert find_saves(folder) == [a, b]
    assert find_saves(a) == [a]
    report = import_saves(storage, catalog, [a])
    assert report.imported == [ID]
    report = import_saves(storage, catalog, [folder])
    assert (report.imported, report.skipped) == ([OTHER], [ID])


@pytest.mark.parametrize(
    ("write", "reason"),
    [
        (lambda f: old_save(f, with_table=False), "partida solo"),
        (
            lambda f: (f / f"{ID}.json").write_text("{isto não é json", encoding="utf-8"),
            "não é uma partida",
        ),
        (
            lambda f: (f / f"{ID}.json").write_text(
                '{"save_version": 1, "state": "SEGREDO"}', encoding="utf-8"
            ),
            "não é uma partida",
        ),
    ],
    ids=["solo", "json-quebrado", "sem-campos"],
)
def test_what_is_not_a_table_is_refused_with_a_reason_and_no_content(world, write, reason):
    catalog, storage, folder = world
    folder.mkdir(parents=True, exist_ok=True)
    write(folder)
    report = import_saves(storage, catalog, [folder])
    assert report.imported == []
    [(name, why)] = report.refused
    assert name == f"{ID}.json"
    assert reason in why
    assert "SEGREDO" not in why
    assert storage.count() == 0


def test_a_campaign_outside_the_campaigns_folder_is_refused(world, tmp_path):
    catalog, storage, folder = world
    path = old_save(folder)
    data = json.loads(path.read_text(encoding="utf-8"))
    outside = tmp_path / "fora" / "x.json"
    outside.parent.mkdir()
    shutil.copy(CAMPAIGN_PATH, outside)
    data["campaign_path"] = os.path.relpath(outside, folder)
    path.write_text(json.dumps(data), encoding="utf-8")
    report = import_saves(storage, catalog, [folder])
    assert [why for _, why in report.refused] == ["a campanha dela está fora da pasta de campanhas"]
    assert storage.count() == 0


def test_a_state_that_does_not_match_the_campaign_is_refused(world):
    catalog, storage, folder = world
    path = old_save(folder)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["state"]["current_location_id"] = "lugar-que-nao-existe"
    path.write_text(json.dumps(data), encoding="utf-8")
    report = import_saves(storage, catalog, [folder])
    assert [why for _, why in report.refused] == [
        "a partida não combina com a campanha ou com as regras"
    ]


def test_a_file_whose_name_is_not_a_table_id_is_refused(world):
    catalog, storage, folder = world
    path = old_save(folder)
    odd = folder / "minha-partida.json"
    shutil.copy(path, odd)
    report = import_saves(storage, catalog, [odd])
    assert [why for _, why in report.refused] == [
        "o nome do arquivo não é um id de mesa (16 letras e números)"
    ]


def test_the_table_limit_applies_to_the_import(tmp_path):
    catalog = Catalog(CAMPAIGN_PATH.parent)
    storage = make_storage(tmp_path / "dados", max_tables=1)
    folder = tmp_path / "antigas"
    old_save(folder, ID)
    old_save(folder, OTHER)
    report = import_saves(storage, catalog, [folder])
    assert len(report.imported) == 1
    assert "máximo de mesas" in report.refused[0][1]


def test_a_preview_changes_nothing_and_says_what_would_enter_and_what_would_be_refused(world):
    catalog, storage, folder = world
    old_save(folder, ID)
    old_save(folder, OTHER, with_table=False)
    report = import_saves(storage, catalog, [folder], apply=False)
    assert report.imported == [ID]
    assert [name for name, _ in report.refused] == [f"{OTHER}.json"]
    assert storage.count() == 0  # nada foi gravado


def test_an_imported_table_plays_with_the_old_token_and_keeps_its_events(tmp_path):
    """Uma mesa jogada de verdade, exportada ao formato antigo e importada: mesmo estado, mesmo log, mesmo token."""
    catalog = Catalog(CAMPAIGN_PATH.parent)
    first = TableService(catalog, make_storage(tmp_path / "a", max_tables=5))
    created = first.create_table(
        CreateTableRequest(campaign_id="sombra-do-vale", host_name="Ana", seed=7)
    )
    joined = first.join_table(
        created.table_id, JoinRequest(name="Bia", invite_code=created.invite_code)
    )
    for token, line in (
        (created.host_token, 'entrar ana "Ana"'),
        (joined.token, 'entrar bia "Bia"'),
    ):
        view = first.get_table(created.table_id, token)
        first.run_command(
            created.table_id, token, CommandRequest(line=line, revision=view.revision)
        )
    session = first.load_session(created.table_id)
    assert session.state.events  # há log para preservar

    folder = tmp_path / "antigas"
    folder.mkdir()
    exported = build_save(session, os.path.relpath(session.campaign_path, folder))
    (folder / f"{created.table_id}.json").write_text(
        exported.model_dump_json(indent=2), encoding="utf-8"
    )

    second = TableService(catalog, make_storage(tmp_path / "b", max_tables=5))
    report = import_saves(second.storage, catalog, [folder])
    assert report.imported == [created.table_id]
    assert second.load_session(created.table_id).state == session.state
    view = second.get_table(created.table_id, created.host_token)
    assert view.revision == len(session.state.events)
    assert second.get_table(created.table_id, joined.token).table_id == created.table_id


# --- o comando `devaneio importar` --------------------------------------------------------


def run_import(tmp_path, *extra, data=None):
    return import_main(
        [
            "--campanhas",
            str(CAMPAIGN_PATH.parent),
            "--dados",
            str(data or tmp_path / "dados"),
            *extra,
        ]
    )


def test_the_import_command_defaults_to_the_data_folder(tmp_path, capsys):
    data = tmp_path / "dados"
    old_save(data)
    assert run_import(tmp_path) == 0
    assert "Importadas: 1." in capsys.readouterr().out
    assert (data / DB_NAME).exists()
    assert run_import(tmp_path) == 0
    assert "Importadas: 0. Já estavam no banco: 1." in capsys.readouterr().out


def test_the_import_command_reports_what_it_refused_and_exits_with_an_error(tmp_path, capsys):
    data = tmp_path / "dados"
    old_save(data, with_table=False)
    assert run_import(tmp_path) == 1
    assert "recusada: " in capsys.readouterr().err


def test_the_import_command_refuses_to_run_while_the_server_holds_the_database(tmp_path, capsys):
    data = prepare_data_dir(tmp_path / "dados")
    held = acquire_instance_lock(data)
    try:
        assert run_import(tmp_path) == 1
    finally:
        held.close()
    assert "um banco, um servidor" in capsys.readouterr().err


def test_the_import_command_is_reached_through_main(tmp_path, capsys):
    old_save(tmp_path / "dados")
    assert (
        main(
            [
                "importar",
                "--campanhas",
                str(CAMPAIGN_PATH.parent),
                "--dados",
                str(tmp_path / "dados"),
            ]
        )
        == 0
    )
    assert "Importadas: 1." in capsys.readouterr().out


def serve_quietly(monkeypatch, tmp_path):
    class Quiet:
        server_address = ("127.0.0.1", 0)

        def serve_forever(self):
            raise KeyboardInterrupt

        def server_close(self):
            pass

    monkeypatch.setattr(entry, "make_server", lambda *_args, **_kwargs: Quiet())
    return entry.main(
        [
            "--campanhas",
            str(CAMPAIGN_PATH.parent),
            "--dados",
            str(tmp_path / "dados"),
            "--sem-navegador",
            "--porta",
            "0",
        ]
    )


def test_the_server_warns_about_old_saves_waiting_for_import(tmp_path, monkeypatch, capsys):
    old_save(tmp_path / "dados")
    assert serve_quietly(monkeypatch, tmp_path) == 0
    err = capsys.readouterr().err
    assert "1 partida(s) em JSON" in err
    assert "devaneio importar" in err
    assert "não podem ser importados" not in err  # nada recusado, nada a listar


def test_the_server_lists_what_the_import_would_refuse_and_why(tmp_path, monkeypatch, capsys):
    data = tmp_path / "dados"
    old_save(data, ID, with_table=False)  # solo
    (data / f"{OTHER}.json").write_text("{isto não é json", encoding="utf-8")
    assert serve_quietly(monkeypatch, tmp_path) == 0
    err = capsys.readouterr().err
    assert "2 arquivo(s) .json na pasta de dados não podem ser importados" in err
    assert f"{ID}.json: é uma partida solo" in err
    assert f"{OTHER}.json: não é uma partida do Devaneio" in err
    assert (
        "rode 'devaneio importar'" not in err
    )  # nada a importar: não pede um importar que não resolve
    assert "SEGREDO" not in err


def test_the_warning_lists_at_most_ten_refused_files(tmp_path, monkeypatch, capsys):
    data = tmp_path / "dados"
    data.mkdir()
    for n in range(13):
        (data / f"{n:016x}.json").write_text("{", encoding="utf-8")
    assert serve_quietly(monkeypatch, tmp_path) == 0
    err = capsys.readouterr().err
    assert err.count("não é uma partida do Devaneio") == 10
    assert "... e mais 3." in err
