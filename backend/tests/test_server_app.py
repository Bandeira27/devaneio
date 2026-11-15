"""TableService sem HTTP: regras da mesa contra o motor real e o disco de verdade."""

import json
from dataclasses import replace
from itertools import count

import pytest

from conftest import CAMPAIGN_PATH
from devaneio.game import load_game, new_game, save_game
from devaneio.llm import LlmConfig
from devaneio.schema import Campaign, GameState
from devaneio.server import ApiFailure, Catalog, Storage, TableService
from devaneio.server.models import (
    CampaignView,
    CreateTableRequest,
    JoinRequest,
    PlayerStateView,
)

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


def join(service, created, name="Bia", invite="convite-fixo"):
    return service.join_table(created.table_id, JoinRequest(invite_code=invite, name=name))


def test_the_host_gets_the_whole_campaign_and_players_only_what_olhar_shows(service, created):
    campaign = service.get_campaign(created.table_id, bearer(created.host_token))
    assert isinstance(campaign, Campaign)
    assert campaign.npcs[0].secrets == ["sabe o caminho secreto para o altar"]

    joined = join(service, created)
    view = service.get_campaign(created.table_id, bearer(joined.token))
    assert isinstance(view, CampaignView)
    assert view.location.id == "vila"
    assert [(e.id, e.name) for e in view.location.exits] == [("floresta", "Floresta Cinzenta")]
    assert [(n.id, n.name) for n in view.npcs] == [("ferreiro", "Bram")]
    assert [b.id for b in view.beats] == ["chegada"]  # os pendentes não aparecem
    dumped = view.model_dump_json()
    for hidden in (
        "secrets",
        "goals",
        "complete_when",
        "sacerdote",
        "confronto",
        "Culto da Sombra",
        "adaga",
    ):
        assert hidden not in dumped


def test_player_state_shows_hostile_but_never_the_numbers_behind_it(service, created):
    path = service.storage.path_for(created.table_id)
    session = load_game(path)
    ferreiro = session.state.npcs["ferreiro"].model_copy(update={"disposition": -5})
    state = session.state.model_copy(update={"npcs": {**session.state.npcs, "ferreiro": ferreiro}})
    save_game(replace(session, state=state))
    joined = join(service, created)
    view = service.get_table(created.table_id, joined.token)
    npc = view.state.npcs["ferreiro"]
    assert npc.hostile is True
    assert npc.model_dump() == {"alive": True, "hp": 10, "max_hp": 10, "hostile": True}


def test_join_gives_a_token_and_stores_only_its_hash(service, created):
    joined = join(service, created)
    assert joined.player_id == "p2"
    assert joined.token.startswith("token-")
    assert [(p.id, p.name, p.role) for p in joined.table.players] == [
        ("p1", "Ana", "host"),
        ("p2", "Bia", "player"),
    ]
    path = service.storage.path_for(created.table_id)
    text = path.read_text(encoding="utf-8")
    assert joined.token not in text
    assert "convite-fixo" not in text
    data = json.loads(text)
    assert len(data["table"]["players"]["p2"]["token_hash"]) == 64
    # o token novo abre a mesa, e o do anfitrião continua valendo
    assert service.get_table(created.table_id, joined.token).table_id == created.table_id
    assert service.get_table(created.table_id, created.host_token).table_id == created.table_id


@pytest.mark.parametrize("table_id", ["0123456789abcdef", "..", "nada"])
def test_join_with_wrong_invite_or_unknown_table_answers_the_same(service, created, table_id):
    with pytest.raises(ApiFailure, match="convite inválido") as unknown:
        service.join_table(table_id, JoinRequest(invite_code="convite-fixo", name="Bia"))
    with pytest.raises(ApiFailure, match="convite inválido") as wrong:
        join(service, created, invite="outro")
    assert (unknown.value.status, unknown.value.code) == (401, "invalid_invite")
    assert (wrong.value.status, wrong.value.code) == (401, "invalid_invite")


def test_join_refuses_a_full_table_and_a_repeated_name(service, created):
    join(service, created, name="Bia")
    with pytest.raises(ApiFailure, match="já existe um jogador chamado 'bia'") as info:
        join(service, created, name="bia")
    assert (info.value.status, info.value.code) == (409, "name_taken")
    for number in range(3, 9):
        join(service, created, name=f"Jogador {number}")
    with pytest.raises(ApiFailure, match="já tem 8 jogadores") as full:
        join(service, created, name="De fora")
    assert (full.value.status, full.value.code) == (409, "table_full")
    # sem o convite certo, ninguém descobre que a mesa está cheia
    with pytest.raises(ApiFailure, match="convite inválido"):
        join(service, created, name="De fora", invite="outro")


def test_players_see_a_projection_of_the_state_and_the_host_sees_it_all(service, created):
    host_view = service.get_table(created.table_id, created.host_token)
    assert isinstance(host_view.state, GameState)
    assert host_view.state.rng_seed == 7
    assert "sacerdote" in host_view.state.npcs

    joined = join(service, created)
    for view in (joined.table, service.get_table(created.table_id, joined.token)):
        assert isinstance(view.state, PlayerStateView)
        dumped = view.state.model_dump()
        assert "rng_seed" not in dumped
        assert "rng_draws" not in dumped
        assert "events" not in dumped
        assert "facts" not in dumped
        assert "confronto" not in dumped["beats"]  # marco pendente
        assert list(view.state.npcs) == ["ferreiro"]  # o sacerdote está nas ruínas
        assert view.state.npcs["ferreiro"].hostile is False
        assert view.role == "player"
        assert view.revision == host_view.revision
    assert host_view.role == "host"


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
    assert "qwen3 em localhost:11434" in llm.notice
    assert "voltam aos jogadores" in llm.notice
    assert "chave" not in created.model_dump_json()


def test_by_default_the_notice_says_npc_secrets_do_not_go_to_the_llm(tmp_path):
    config = LlmConfig(base_url="http://localhost:11434/v1", model="qwen3")
    llm = (
        make_service(tmp_path, llm=config)
        .create_table(CreateTableRequest(campaign_id="sombra-do-vale", host_name="Ana"))
        .table.llm
    )
    assert llm.secrets is False
    assert "Os segredos dos NPCs não vão." in llm.notice
    assert "com seus segredos" not in llm.notice


def test_when_the_host_opts_in_the_notice_says_the_secrets_go_and_the_speech_reaches_all(tmp_path):
    config = LlmConfig(base_url="http://localhost:11434/v1", model="qwen3")
    llm = (
        make_service(tmp_path, llm=config, llm_secrets=True)
        .create_table(CreateTableRequest(campaign_id="sombra-do-vale", host_name="Ana"))
        .table.llm
    )
    assert llm.secrets is True
    assert "NPCs presentes com seus segredos" in llm.notice
    assert "Os segredos dos NPCs não vão." not in llm.notice


def test_without_an_llm_the_table_says_secrets_are_not_shared(tmp_path):
    created = make_service(tmp_path).create_table(
        CreateTableRequest(campaign_id="sombra-do-vale", host_name="Ana")
    )
    assert created.table.llm.model_dump() == {
        "enabled": False,
        "description": None,
        "notice": None,
        "secrets": False,
    }


def test_llm_view_never_shows_user_and_password_from_the_url(tmp_path):
    config = LlmConfig(base_url="http://alice:S3NHA@localhost:11434/v1", model="qwen3")
    service = make_service(tmp_path, llm=config)
    created = service.create_table(
        CreateTableRequest(campaign_id="sombra-do-vale", host_name="Ana")
    )
    assert created.table.llm.description == "qwen3 em localhost:11434"
    assert "S3NHA" not in created.model_dump_json()
    assert "alice" not in created.model_dump_json()


@pytest.mark.parametrize(
    "name",
    ["Ana ", " ana", "ANA", chr(0xFF21) + "na"],
    ids=["espaco", "inicio", "caixa", "largura-total"],
)
def test_a_name_that_looks_like_an_existing_one_is_taken(service, created, name):
    with pytest.raises(ApiFailure) as info:
        join(service, created, name=name)
    assert info.value.code == "name_taken"
