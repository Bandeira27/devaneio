"""TableService sem HTTP: regras da mesa contra o motor real e o disco de verdade."""

import json
from itertools import count

import pytest

from conftest import CAMPAIGN_PATH
from devaneio.game import load_game, new_game, save_game
from devaneio.llm import LlmConfig
from devaneio.server import ApiFailure, Catalog, Storage, TableService
from devaneio.server.models import CreateTableRequest

TOKENS = count(1)


def make_service(tmp_path, **kwargs):
    kwargs.setdefault("token_source", lambda: f"token-{next(TOKENS)}")
    kwargs.setdefault("invite_source", lambda: "convite-fixo")
    return TableService(
        Catalog(CAMPAIGN_PATH.parent),
        Storage(tmp_path / "mesas", max_tables=kwargs.pop("max_tables", 10)),
        **kwargs,
    )


def bearer(token):
    return token


@pytest.fixture
def service(tmp_path):
    return make_service(tmp_path)


@pytest.fixture
def created(service):
    return service.create_table(
        CreateTableRequest(campaign_id="sombra-do-vale", host_name="Ana", seed=7)
    )


def test_catalog_lists_the_campaigns_of_the_folder(service):
    [summary] = service.list_campaigns()
    assert summary.id == "sombra-do-vale"
    assert summary.title == "A Sombra do Vale"


def test_catalog_rejects_duplicated_ids_and_broken_files(tmp_path):
    folder = tmp_path / "campanhas"
    folder.mkdir()
    text = CAMPAIGN_PATH.read_text(encoding="utf-8")
    (folder / "a.json").write_text(text, encoding="utf-8")
    (folder / "b.json").write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match=r"'sombra-do-vale' repetida: a\.json e b\.json"):
        Catalog(folder)
    (folder / "b.json").write_text('{"id": "x"}', encoding="utf-8")
    with pytest.raises(ValueError, match=r"campanha 'b\.json' inválida"):
        Catalog(folder)


def test_catalog_ignores_files_that_are_not_json(tmp_path):
    folder = tmp_path / "campanhas"
    folder.mkdir()
    (folder / "vale.json").write_text(CAMPAIGN_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    (folder / "rascunho.json.bak").write_text("{", encoding="utf-8")
    (folder / "LEIAME.md").write_text("# nada", encoding="utf-8")
    (folder / "sub").mkdir()
    catalog = Catalog(folder)
    assert [s.id for s in catalog.summaries()] == ["sombra-do-vale"]
    assert catalog.path("sombra-do-vale") == folder.resolve() / "vale.json"
    assert catalog.path("rascunho") is None


def test_create_table_writes_the_save_with_the_table(service, created, tmp_path):
    assert created.host_token.startswith("token-")
    assert created.invite_code == "convite-fixo"
    view = created.table
    assert view.table_id == created.table_id
    assert view.campaign.id == "sombra-do-vale"
    assert [p.model_dump() for p in view.players] == [
        {"id": "p1", "name": "Ana", "role": "host", "character_ids": []}
    ]
    assert view.turn_policy == "one_action_per_character"
    assert view.revision == 1  # marco inicial ativado
    assert view.status.value == "active"
    assert view.llm.enabled is False
    assert view.state.rng_seed == 7

    path = tmp_path / "mesas" / f"{created.table_id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["table"]["players"]["p1"]["token_hash"] != created.host_token
    assert len(data["table"]["players"]["p1"]["token_hash"]) == 64
    assert created.host_token not in path.read_text(encoding="utf-8")
    assert created.invite_code not in path.read_text(encoding="utf-8")
    # a partida é uma partida normal: o CLI abre e preserva a mesa
    session = load_game(path)
    assert session.table is not None
    assert session.table.players["p1"].name == "Ana"


def test_create_table_unknown_campaign_and_limit(tmp_path):
    service = make_service(tmp_path, max_tables=1)
    with pytest.raises(ApiFailure, match="campanha 'nada' não existe") as info:
        service.create_table(CreateTableRequest(campaign_id="nada", host_name="Ana"))
    assert (info.value.status, info.value.code) == (404, "campaign_not_found")
    service.create_table(CreateTableRequest(campaign_id="sombra-do-vale", host_name="Ana"))
    with pytest.raises(ApiFailure, match="máximo de mesas") as info:
        service.create_table(CreateTableRequest(campaign_id="sombra-do-vale", host_name="Bia"))
    assert info.value.status == 409


def test_get_table_requires_a_valid_token(service, created):
    view = service.get_table(created.table_id, bearer(created.host_token))
    assert view.model_dump() == created.table.model_dump()
    for token, message in ((None, "token ausente"), ("token-errado", "token inválido")):
        with pytest.raises(ApiFailure, match=message) as info:
            service.get_table(created.table_id, token)
        assert info.value.status == 401


@pytest.mark.parametrize(
    "table_id",
    [
        "",
        "..",
        "../x",
        "%2e%2e",
        "0123456789abcdef0",
        "0123456789ABCDEF",
        "x" * 16,
        "0123456789abcdef",
    ],
)
def test_get_table_rejects_ids_it_did_not_generate(service, created, table_id, monkeypatch):
    def never(*_args, **_kwargs):
        raise AssertionError("nenhum arquivo deveria ser aberto para esse id")

    monkeypatch.setattr("devaneio.server.app.load_game", never)
    with pytest.raises(ApiFailure, match="mesa não encontrada") as info:
        service.get_table(table_id, bearer(created.host_token))
    assert info.value.status == 404


def test_a_save_without_table_in_the_data_folder_is_not_a_table(service, created):
    """Uma partida solo copiada para a pasta de dados não vira mesa."""
    table_id = "0123456789abcdef"
    save_game(new_game(CAMPAIGN_PATH, service.storage.data_dir / f"{table_id}.json", seed=7))
    with pytest.raises(ApiFailure, match="mesa não encontrada") as info:
        service.get_table(table_id, bearer(created.host_token))
    assert info.value.status == 404


def test_campaign_hides_npc_secrets_from_players_but_not_from_the_host(service, created):
    campaign = service.get_campaign(created.table_id, bearer(created.host_token))
    assert campaign.npcs[0].secrets == ["sabe o caminho secreto para o altar"]
    # um jogador comum entra em `players` só na etapa 2: por ora, simula um no arquivo
    session = load_game(service.storage.path_for(created.table_id))
    assert session.table is not None
    player = session.table.players["p1"].model_copy(update={"role": "player"})
    session.table.players["p1"] = player
    save_game(session)
    campaign = service.get_campaign(created.table_id, bearer(created.host_token))
    assert [n.secrets for n in campaign.npcs] == [[], []]
    assert campaign.npcs[0].name == "Bram"


def test_unreadable_save_is_an_internal_error_without_the_file_contents(service, created):
    path = service.storage.path_for(created.table_id)
    path.write_text('{"save_version": 1, "campaign_path": "x.json", "state": "SEGREDO"}')
    with pytest.raises(RuntimeError, match="partida ilegível") as info:
        service.get_table(created.table_id, bearer(created.host_token))
    assert "SEGREDO" not in str(info.value)
    assert service.storage.lock(created.table_id).locked() is False


def test_campaign_outside_the_catalog_is_refused(service, created, tmp_path):
    path = service.storage.path_for(created.table_id)
    outside = tmp_path / "fora.json"
    outside.write_text(CAMPAIGN_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["campaign_path"] = "../fora.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(RuntimeError, match="partida ilegível"):
        service.get_table(created.table_id, bearer(created.host_token))


def test_llm_view_tells_players_where_the_context_goes(tmp_path):
    config = LlmConfig(base_url="http://localhost:11434/v1", model="qwen3", api_key="chave")
    service = make_service(tmp_path, llm=config)
    created = service.create_table(
        CreateTableRequest(campaign_id="sombra-do-vale", host_name="Ana")
    )
    llm = created.table.llm
    assert llm.enabled is True
    assert llm.description == "qwen3 em localhost:11434"
    assert "segredos" in llm.notice
    assert "qwen3 em localhost:11434" in llm.notice
    assert "chave" not in created.model_dump_json()


def test_llm_view_never_shows_user_and_password_from_the_url(tmp_path):
    config = LlmConfig(base_url="http://alice:S3NHA@localhost:11434/v1", model="qwen3")
    service = make_service(tmp_path, llm=config)
    created = service.create_table(
        CreateTableRequest(campaign_id="sombra-do-vale", host_name="Ana")
    )
    assert created.table.llm.description == "qwen3 em localhost:11434"
    assert "S3NHA" not in created.model_dump_json()
    assert "alice" not in created.model_dump_json()
