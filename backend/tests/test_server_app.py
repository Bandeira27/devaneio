"""TableService sem HTTP: regras da mesa contra o motor real e o disco de verdade."""

import json
from dataclasses import replace
from itertools import count

import pytest

from conftest import CAMPAIGN_PATH
from devaneio.engine import reveal_fact
from devaneio.game import load_game, new_game, save_game
from devaneio.llm import LlmConfig
from devaneio.schema import Campaign, GameState
from devaneio.server import ApiFailure, Catalog, Storage, TableService
from devaneio.server.models import (
    CampaignView,
    CreateTableRequest,
    InvitePreview,
    InvitePreviewRequest,
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


def test_players_see_a_fact_only_after_it_is_revealed(service, created):
    joined = join(service, created)
    before = service.get_campaign(created.table_id, bearer(joined.token))
    assert before.facts == []

    session = load_game(service.storage.path_for(created.table_id))
    revealed = reveal_fact(session.state, session.campaign, fact_id="ferreiro-segredo").state
    save_game(replace(session, state=revealed))
    after = service.get_campaign(created.table_id, bearer(joined.token))
    assert [(f.id, f.text) for f in after.facts] == [
        ("ferreiro-segredo", "Bram conhece o caminho secreto para o altar.")
    ]
    view = service.get_table(created.table_id, joined.token)
    assert view.state.revealed_facts == {"ferreiro-segredo": 0}


def test_the_host_gets_the_whole_campaign_and_players_only_what_olhar_shows(service, created):
    campaign = service.get_campaign(created.table_id, bearer(created.host_token))
    assert isinstance(campaign, Campaign)
    assert campaign.facts[0].text == "Bram conhece o caminho secreto para o altar."

    joined = join(service, created)
    view = service.get_campaign(created.table_id, bearer(joined.token))
    assert isinstance(view, CampaignView)
    assert view.location.id == "vila"
    assert [(e.id, e.name) for e in view.location.exits] == [("floresta", "Floresta Cinzenta")]
    assert [(n.id, n.name) for n in view.npcs] == [("ferreiro", "Bram")]
    assert [b.id for b in view.beats] == ["chegada"]  # os pendentes não aparecem
    dumped = view.model_dump_json()
    for hidden in (
        "caminho secreto",
        "líder do culto",
        "private_notes",
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


def test_invite_preview_shows_only_the_campaign_title(service, created):
    preview = service.preview_invite(
        created.table_id, InvitePreviewRequest(invite_code="convite-fixo")
    )
    assert preview == InvitePreview(title="A Sombra do Vale")


def test_invite_preview_contract_is_only_the_title():
    # nada de id da campanha, premissa, jogadores ou mesa
    assert set(InvitePreview.model_fields) == {"title"}


@pytest.mark.parametrize("table_id", ["0123456789abcdef", "..", "nada"])
def test_invite_preview_with_wrong_invite_or_unknown_table_answers_like_join(
    service, created, table_id
):
    with pytest.raises(ApiFailure) as unknown:
        service.preview_invite(table_id, InvitePreviewRequest(invite_code="convite-fixo"))
    with pytest.raises(ApiFailure) as wrong:
        service.preview_invite(created.table_id, InvitePreviewRequest(invite_code="outro"))
    with pytest.raises(ApiFailure) as join_wrong:
        join(service, created, invite="outro")
    same = (join_wrong.value.status, join_wrong.value.code, join_wrong.value.message)
    assert (unknown.value.status, unknown.value.code, unknown.value.message) == same
    assert (wrong.value.status, wrong.value.code, wrong.value.message) == same


def test_invite_preview_does_not_depend_on_the_table_being_full(service, created):
    for i in range(7):  # anfitrião + 7 = 8, o máximo
        join(service, created, name=f"Jogador{i}")
    preview = service.preview_invite(
        created.table_id, InvitePreviewRequest(invite_code="convite-fixo")
    )
    assert preview.title == "A Sombra do Vale"  # a prévia não é oráculo de "mesa cheia"


def test_invite_preview_of_a_save_without_table_answers_like_an_unknown_table(service, created):
    table_id = "0123456789abcdef"
    save_game(new_game(CAMPAIGN_PATH, service.storage.data_dir / f"{table_id}.json", seed=7))
    with pytest.raises(ApiFailure, match="convite inválido") as info:
        service.preview_invite(table_id, InvitePreviewRequest(invite_code="convite-fixo"))
    assert (info.value.status, info.value.code) == (401, "invalid_invite")


def test_invite_preview_of_another_table_with_its_own_invite_is_refused(tmp_path):
    codes = iter(["convite-a", "convite-b"])
    service = make_service(tmp_path, invite_source=lambda: next(codes))
    request = CreateTableRequest(campaign_id="sombra-do-vale", host_name="Ana", seed=7)
    first = service.create_table(request)
    second = service.create_table(request)
    other = InvitePreviewRequest(invite_code="convite-b")
    with pytest.raises(ApiFailure, match="convite inválido") as info:
        service.preview_invite(first.table_id, other)
    assert (info.value.status, info.value.code) == (401, "invalid_invite")
    assert service.preview_invite(second.table_id, other).title == "A Sombra do Vale"


def test_invite_preview_changes_nothing_on_disk(service, created):
    path = service.storage.data_dir / f"{created.table_id}.json"
    before = path.read_bytes()
    service.preview_invite(created.table_id, InvitePreviewRequest(invite_code="convite-fixo"))
    assert path.read_bytes() == before


def test_invite_preview_request_accepts_sixty_four_characters():
    assert InvitePreviewRequest(invite_code="x" * 64).invite_code == "x" * 64


@pytest.mark.parametrize("code", ["", "x" * 65])
def test_invite_preview_request_rejects_empty_and_sixty_five_characters(code):
    with pytest.raises(ValueError, match="invite_code"):
        InvitePreviewRequest(invite_code=code)


def test_invite_preview_request_rejects_extra_fields():
    with pytest.raises(ValueError, match="extra"):
        InvitePreviewRequest.model_validate({"invite_code": "x", "name": "Bia"})


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
    assert "Segredos, fatos ocultos e notas privadas não vão." in llm.notice
    assert "fatos ocultos e notas privadas da campanha" not in llm.notice


def test_when_the_host_opts_in_the_notice_says_the_secrets_go_and_the_speech_reaches_all(tmp_path):
    config = LlmConfig(base_url="http://localhost:11434/v1", model="qwen3")
    llm = (
        make_service(tmp_path, llm=config, llm_secrets=True)
        .create_table(CreateTableRequest(campaign_id="sombra-do-vale", host_name="Ana"))
        .table.llm
    )
    assert llm.secrets is True
    assert "fatos ocultos e notas privadas da campanha" in llm.notice
    assert "Segredos, fatos ocultos e notas privadas não vão." not in llm.notice


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


def test_the_server_logs_a_changed_content_warning_once_per_table(service, created, capsys):
    path = service.storage.path_for(created.table_id)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["content"] = {"rules_sha256": "0" * 64, "narration_sha256": "0" * 64}
    path.write_text(json.dumps(data), encoding="utf-8")
    service.get_table(created.table_id, bearer(created.host_token))
    service.get_table(created.table_id, bearer(created.host_token))
    err = capsys.readouterr().err
    assert err.count("O sistema de regras 'default' mudou") == 1
    assert err.count("O pacote de narração 'pt-br' mudou") == 1


def test_a_second_content_change_warns_again_after_a_save(service, created, capsys):
    path = service.storage.path_for(created.table_id)

    def stale():
        data = json.loads(path.read_text(encoding="utf-8"))
        data["content"] = {"rules_sha256": "0" * 64, "narration_sha256": "0" * 64}
        path.write_text(json.dumps(data), encoding="utf-8")

    stale()
    service.get_table(created.table_id, bearer(created.host_token))
    save_game(load_game(path))  # o salvamento grava o conteúdo atual
    service.get_table(created.table_id, bearer(created.host_token))
    capsys.readouterr()
    stale()
    service.get_table(created.table_id, bearer(created.host_token))
    assert "mudou desde que esta partida foi salva" in capsys.readouterr().err


def test_the_notice_tells_everyone_about_the_hosts_copilot(tmp_path):
    config = LlmConfig(base_url="http://127.0.0.1:9/v1", model="m")
    for secrets in (False, True):
        service = make_service(tmp_path / str(secrets), llm=config, llm_secrets=secrets)
        created = service.create_table(
            CreateTableRequest(campaign_id="sombra-do-vale", host_name="Ana", seed=7)
        )
        notice = service.get_table(created.table_id, created.host_token).llm.notice
        assert "copiloto" in notice
        assert "volta só ao anfitrião" in notice


# --- catálogo de regras e quem sou eu -----------------------------------------------------


def test_every_view_says_who_is_asking(service, created):
    host_view = service.get_table(created.table_id, created.host_token)
    assert host_view.you == "p1"
    assert created.table.you == "p1"  # a resposta da criação já diz
    joined = join(service, created)
    assert joined.table.you == "p2"
    assert service.get_table(created.table_id, joined.token).you == "p2"
    assert service.get_table(created.table_id, created.host_token).you == "p1"


def test_the_rules_catalog_is_open_to_any_player_with_a_token(service, created):
    joined = join(service, created)
    for token in (created.host_token, joined.token):
        rules = service.get_rules(created.table_id, bearer(token))
        assert rules.id == "default"
        assert [a.id for a in rules.attributes] == ["FOR", "AGI", "MEN", "PRE"]
        attribute = rules.attributes[0]
        assert (attribute.min, attribute.max, attribute.default) == (1, 5, 2)
        assert {s.id for s in rules.skills} >= {"lutar", "persuadir"}
        assert next(s for s in rules.skills if s.id == "lutar").formula == "2d6 + FOR"
        assert [d.id for d in rules.difficulties] == ["facil", "normal", "dificil", "heroica"]
        assert {w.id for w in rules.weapons} >= {"punhos", "adaga"}
        assert {m.id for m in rules.modifiers} == {"vantagem", "desvantagem"}
        assert rules.combat.default_weapon == "punhos"
        assert rules.combat.fallen_can_act is False


def test_the_rules_catalog_leaves_out_what_no_screen_uses(service, created):
    dumped = service.get_rules(created.table_id, bearer(created.host_token)).model_dump_json()
    for left_out in ("max_hp", "hostile_below", "critical_success_margin", "heal"):
        assert left_out not in dumped


def test_the_rules_catalog_needs_a_valid_token_and_an_existing_table(service, created):
    with pytest.raises(ApiFailure) as info:
        service.get_rules(created.table_id, None)
    assert info.value.status == 401
    with pytest.raises(ApiFailure) as info:
        service.get_rules(created.table_id, "token-errado")
    assert info.value.status == 401
    with pytest.raises(ApiFailure) as info:
        service.get_rules("0" * 16, bearer(created.host_token))
    assert info.value.status == 404


def test_the_rules_catalog_shows_the_authors_system_when_the_campaign_extends_one(tmp_path):
    data = json.loads(CAMPAIGN_PATH.read_text(encoding="utf-8"))
    data["id"] = "com-magia"
    data["rules_id"] = "meu-sistema"
    folder = tmp_path / "campanhas"
    (folder / "sistemas").mkdir(parents=True)
    (folder / "campanha.json").write_text(json.dumps(data), encoding="utf-8")
    system = {
        "id": "meu-sistema",
        "extends": "default",
        "name": "Meu Sistema",
        "skills": [{"id": "magia", "name": "Magia", "formula": "2d6 + MEN"}],
    }
    (folder / "sistemas" / "meu-sistema.json").write_text(json.dumps(system), encoding="utf-8")
    service = TableService(
        Catalog(folder),
        Storage(tmp_path / "mesas", max_tables=2),
        token_source=lambda: "token-x",
        invite_source=lambda: "convite-x",
    )
    created = service.create_table(
        CreateTableRequest(campaign_id="com-magia", host_name="Ana", seed=1)
    )
    rules = service.get_rules(created.table_id, created.host_token)
    assert rules.name == "Meu Sistema"
    assert "magia" in {s.id for s in rules.skills}


def test_the_last_seat_of_a_full_table_knows_it_is_p8(service, created):
    joined = None
    for number in range(2, 9):
        joined = join(service, created, name=f"Jogador {number}")
    assert joined.player_id == "p8"
    assert joined.table.you == "p8"
    assert service.get_table(created.table_id, joined.token).you == "p8"
    assert service.get_table(created.table_id, created.host_token).you == "p1"
