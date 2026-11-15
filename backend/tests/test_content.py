import json

import pytest

from devaneio.game import GameError, load_campaign_content, load_game, new_game, save_game
from devaneio.game.content import MAX_CONTENT_BYTES
from devaneio.narration import builtin_pack_dict
from devaneio.rules import builtin_rules_dict
from devaneio.server import Catalog
from devaneio.server.catalog import CatalogError


@pytest.fixture
def folder(tmp_path, campaign_data):
    """Pasta de campanhas com a campanha de exemplo pedindo sistema e narração do autor."""
    campaign_data["rules_id"] = "meu-sistema"
    campaign_data["narration_id"] = "meu-estilo"
    (tmp_path / "campanha.json").write_text(json.dumps(campaign_data), encoding="utf-8")
    return tmp_path


def write(folder, directory, name, data):
    target = folder / directory
    target.mkdir(exist_ok=True)
    text = data if isinstance(data, str) else json.dumps(data)
    (target / f"{name}.json").write_text(text, encoding="utf-8")


def good_rules(**fields):
    return {"id": "meu-sistema", "extends": "default", "name": "Meu Sistema", **fields}


def good_pack(**fields):
    return {"id": "meu-estilo", "extends": "pt-br", **fields}


def load(folder):
    return load_campaign_content(folder / "campanha.json")


def test_the_authors_files_are_used(folder):
    write(folder, "sistemas", "meu-sistema", good_rules())
    write(folder, "narracoes", "meu-estilo", good_pack(rules={"turn_end": ["Fim do #turno#."]}))
    _, rules, pack = load(folder)
    assert rules.id == "meu-sistema"
    assert rules.name == "Meu Sistema"
    assert pack.id == "meu-estilo"
    assert pack.rules["turn_end"] == ["Fim do #turno#."]


def test_a_new_game_narrates_with_the_authors_pack(folder):
    write(folder, "sistemas", "meu-sistema", good_rules())
    write(folder, "narracoes", "meu-estilo", good_pack(rules={"turn_end": ["Fim do #turno#."]}))
    session = new_game(folder / "campanha.json", folder / "partida.json", seed=1)
    assert session.narrator.pack.rules["turn_end"] == ["Fim do #turno#."]


def test_the_builtin_ones_still_work_without_files(tmp_path, campaign_data):
    (tmp_path / "campanha.json").write_text(json.dumps(campaign_data), encoding="utf-8")
    _, rules, pack = load(tmp_path)
    assert rules.id == "default"
    assert pack.id == "pt-br"


def test_the_parent_of_an_extension_can_be_the_authors_own_file(folder):
    base = builtin_rules_dict("default") | {"id": "base", "name": "Base"}
    write(folder, "sistemas", "base", base)
    write(folder, "sistemas", "meu-sistema", good_rules(extends="base"))
    write(folder, "narracoes", "base-voz", builtin_pack_dict("pt-br") | {"id": "base-voz"})
    write(folder, "narracoes", "meu-estilo", good_pack(extends="base-voz"))
    _, rules, pack = load(folder)
    assert (rules.id, pack.id) == ("meu-sistema", "meu-estilo")


def test_a_missing_system_or_pack_says_where_it_looked(folder):
    with pytest.raises(GameError, match=r"'meu-sistema' não encontrado.*sistemas/"):
        load(folder)
    write(folder, "sistemas", "meu-sistema", good_rules())
    with pytest.raises(GameError, match=r"'meu-estilo' não encontrado.*narracoes/"):
        load(folder)
    write(folder, "narracoes", "meu-estilo", good_pack(extends="nada"))
    with pytest.raises(GameError, match=r"'nada' não encontrado"):
        load(folder)


def test_the_file_id_must_match_what_the_campaign_asks(folder):
    write(folder, "sistemas", "meu-sistema", good_rules(id="outro"))
    with pytest.raises(GameError, match="pede o sistema 'meu-sistema', mas o sistema é 'outro'"):
        load(folder)


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        ("{ não é json", "JSON inválido na linha 1"),
        ("[1, 2]", "precisa ser um objeto JSON"),
        (json.dumps(good_rules(skils=[])), "skils"),
        (
            json.dumps(good_rules(skills=[{"id": "x", "name": "X", "formula": "2d6 + SORTE"}])),
            "SORTE",
        ),
    ],
    ids=["syntax", "not-an-object", "unknown-field", "integrity"],
)
def test_a_broken_system_file_is_a_game_error_in_portuguese(folder, text, fragment):
    write(folder, "sistemas", "meu-sistema", text)
    with pytest.raises(GameError, match=fragment) as info:
        load(folder)
    assert str(folder) not in str(info.value)


def test_a_chain_of_extends_is_refused(folder):
    write(
        folder,
        "sistemas",
        "base",
        builtin_rules_dict("default") | {"id": "base", "extends": "default"},
    )
    write(folder, "sistemas", "meu-sistema", good_rules(extends="base"))
    with pytest.raises(GameError, match="só um nível"):
        load(folder)


def test_a_file_that_is_too_big_is_refused_before_reading(folder):
    write(folder, "sistemas", "meu-sistema", " " * (MAX_CONTENT_BYTES + 1))
    with pytest.raises(GameError, match="arquivo maior que"):
        load(folder)


def test_a_symlink_to_outside_the_campaign_folder_is_refused(folder, tmp_path_factory):
    outside = tmp_path_factory.mktemp("fora") / "x.json"
    outside.write_text(json.dumps(good_rules()), encoding="utf-8")
    (folder / "sistemas").mkdir()
    (folder / "sistemas" / "meu-sistema.json").symlink_to(outside)
    with pytest.raises(GameError, match="fora da pasta da campanha"):
        load(folder)


def test_the_server_catalog_checks_the_content_at_startup(folder):
    with pytest.raises(CatalogError, match="não encontrado"):
        Catalog(folder)
    write(folder, "sistemas", "meu-sistema", good_rules())
    write(folder, "narracoes", "meu-estilo", good_pack())
    assert [c.id for c in Catalog(folder).summaries()] == ["sombra-do-vale"]


# --- impressão digital do conteúdo ------------------------------------------------------


def start(folder):
    write(folder, "sistemas", "meu-sistema", good_rules())
    write(folder, "narracoes", "meu-estilo", good_pack())
    session = new_game(folder / "campanha.json", folder / "partida.json", seed=1)
    return session, folder / "partida.json"


def test_reopening_an_unchanged_game_has_no_warnings(folder):
    _, save = start(folder)
    assert load_game(save).warnings == ()


def test_changing_the_system_or_the_pack_warns_which_one(folder):
    _, save = start(folder)
    write(
        folder,
        "sistemas",
        "meu-sistema",
        good_rules(name="Meu Sistema", combat={"fallen_can_act": True}),
    )
    (warning,) = load_game(save).warnings
    assert warning.startswith("O sistema de regras 'meu-sistema' mudou")

    write(folder, "narracoes", "meu-estilo", good_pack(rules={"turn_end": ["Fim #turno#."]}))
    rules_warning, pack_warning = load_game(save).warnings
    assert rules_warning.startswith("O sistema de regras")
    assert pack_warning.startswith("O pacote de narração 'meu-estilo' mudou")


def test_saving_again_accepts_the_new_content(folder):
    _, save = start(folder)
    write(folder, "narracoes", "meu-estilo", good_pack(rules={"turn_end": ["Fim #turno#."]}))
    session = load_game(save)
    assert session.warnings
    save_game(session)
    assert load_game(save).warnings == ()


def test_reordering_the_json_keys_is_not_a_change(folder):
    _, save = start(folder)
    reordered = dict(reversed(list(good_rules().items())))
    write(folder, "sistemas", "meu-sistema", reordered)
    assert load_game(save).warnings == ()


def test_an_old_save_without_content_opens_without_warnings(folder):
    _, save = start(folder)
    data = json.loads(save.read_text(encoding="utf-8"))
    del data["content"]
    save.write_text(json.dumps(data), encoding="utf-8")
    write(folder, "sistemas", "meu-sistema", good_rules(name="Mudou"))
    assert load_game(save).warnings == ()
