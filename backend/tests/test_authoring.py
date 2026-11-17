import json
import subprocess
import sys
from datetime import date
from typing import Literal

import pytest
from pydantic import BaseModel, Field, ValidationError

from conftest import CAMPAIGN_PATH
from devaneio.game import check_content, explain_validation_error
from devaneio.game.authoring import _CONDITION_KINDS
from devaneio.narration import builtin_pack_dict, lint_pack, load_builtin_pack, load_pack
from devaneio.schema import Campaign


@pytest.fixture
def pack():
    return load_builtin_pack("pt-br")


def findings(campaign_data, rules, pack):
    return [str(f) for f in check_content(Campaign.model_validate(campaign_data), rules, pack)]


def test_the_example_campaign_has_nothing_to_report(campaign, rules, pack):
    assert check_content(campaign, rules, pack) == []


def test_a_check_passed_with_an_unknown_skill_is_an_error(campaign_data, rules, pack):
    campaign_data["facts"][0]["reveal_when"] = [{"kind": "check_passed", "skill_id": "magia"}]
    assert findings(campaign_data, rules, pack) == [
        "erro: fato 'ferreiro-segredo', reveal_when: a habilidade 'magia' não existe no "
        "sistema 'default'; a condição nunca vale"
    ]


def test_a_check_passed_with_a_known_skill_is_fine(campaign_data, rules, pack):
    campaign_data["facts"][0]["reveal_when"] = [{"kind": "check_passed", "skill_id": "persuadir"}]
    assert findings(campaign_data, rules, pack) == []


def test_npc_down_without_the_location_warns_for_beats_and_facts(campaign_data, rules, pack):
    campaign_data["beats"][2]["complete_when"] = [{"kind": "npc_down", "npc_id": "sacerdote"}]
    campaign_data["facts"][1]["reveal_when"] = [{"kind": "npc_down", "npc_id": "sacerdote"}]
    got = findings(campaign_data, rules, pack)
    assert len(got) == 2
    assert got[0].startswith(
        "aviso: marco 'confronto', complete_when: depende da queda de 'sacerdote'"
    )
    assert "em 'ruinas'" in got[0]
    assert got[1].startswith("aviso: fato 'sacerdote-segredo', reveal_when:")


def test_npc_down_with_the_location_does_not_warn(campaign_data, rules, pack):
    campaign_data["facts"][1]["reveal_when"] = [
        {"kind": "npc_down", "npc_id": "sacerdote"},
        {"kind": "at_location", "location_id": "ruinas"},
    ]
    assert findings(campaign_data, rules, pack) == []


def test_an_npc_without_a_starting_location_never_warns(campaign_data, rules, pack):
    del campaign_data["npcs"][1]["location_id"]
    campaign_data["facts"][1]["reveal_when"] = [{"kind": "npc_down", "npc_id": "sacerdote"}]
    assert findings(campaign_data, rules, pack) == []


def lint(**rules):
    data = builtin_pack_dict("pt-br")
    data["rules"].update(rules)
    return lint_pack(load_pack(data))


def test_the_builtin_pack_has_no_warnings(pack):
    assert lint_pack(pack) == []


def test_a_variant_the_narrator_does_not_use_warns():
    assert lint(**{"check.sucesso": ["ok"]}) == [
        "regra 'check.sucesso': o narrador não usa a variante 'sucesso' de 'check' "
        "(variantes: critical_failure, failure, success, critical_success); ela nunca dispara"
    ]
    assert "variantes: nenhuma" in lint(**{"move.rapido": ["ok"]})[0]


def test_an_unknown_event_type_with_a_dot_warns():
    (warning,) = lint(**{"chek.success": ["ok"]})
    assert warning.startswith("regra 'chek.success': 'chek' não é um tipo de evento")


def test_an_unreachable_auxiliary_rule_warns_but_a_used_one_does_not():
    assert lint(sobrando=["texto"]) == ["regra auxiliar 'sobrando': nenhuma regra de evento a usa"]
    assert lint(usada=["texto"], **{"move": ["#usada#"]}) == []


def test_an_event_type_without_rules_warns():
    data = builtin_pack_dict("pt-br")
    del data["rules"]["turn_end"]
    del data["rules"]["respiro"]  # auxiliar que só o turn_end usava
    assert lint_pack(load_pack(data)) == [
        "não há regra para o evento 'turn_end': o jogador verá o texto mecânico dele"
    ]


def run_verify(path):
    return subprocess.run(
        [sys.executable, "-m", "devaneio.cli", "verificar", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_verificar_is_clean_on_the_example():
    result = run_verify(CAMPAIGN_PATH)
    assert result.returncode == 0
    assert "nenhum problema encontrado" in result.stdout


def test_verificar_exits_1_on_an_error_and_0_on_a_warning(tmp_path, campaign_data):
    campaign_data["facts"][0]["reveal_when"] = [{"kind": "check_passed", "skill_id": "magia"}]
    path = tmp_path / "c.json"
    path.write_text(json.dumps(campaign_data), encoding="utf-8")
    bad = run_verify(path)
    assert bad.returncode == 1
    assert "erro: fato 'ferreiro-segredo'" in bad.stdout

    campaign_data["facts"][0]["reveal_when"] = []
    campaign_data["facts"][1]["reveal_when"] = [{"kind": "npc_down", "npc_id": "sacerdote"}]
    path.write_text(json.dumps(campaign_data), encoding="utf-8")
    warned = run_verify(path)
    assert warned.returncode == 0
    assert warned.stdout.startswith("aviso:")


def test_verificar_reports_a_broken_campaign_without_a_traceback(tmp_path, campaign_data):
    campaign_data["rules_id"] = "nao-existe"
    path = tmp_path / "c.json"
    path.write_text(json.dumps(campaign_data), encoding="utf-8")
    result = run_verify(path)
    assert result.returncode == 1
    assert "'nao-existe' não encontrado" in result.stderr
    assert "Traceback" not in result.stderr


def test_replacing_a_valid_variant_does_not_warn():
    assert not [w for w in lint(**{"check.success": ["ok"]}) if "variante" in w]


def test_an_auxiliary_rule_reached_only_through_another_auxiliary_does_not_warn():
    assert lint(fundo=["#folha#"], folha=["texto"], move=["#fundo#"]) == []


def test_findings_of_rules_and_narration_come_together(campaign_data, rules):
    data = builtin_pack_dict("pt-br")
    data["rules"]["sobra"] = ["x"]
    campaign_data["facts"][0]["reveal_when"] = [{"kind": "check_passed", "skill_id": "magia"}]
    first, second = findings(campaign_data, rules, load_pack(data))
    assert first.startswith("erro: fato 'ferreiro-segredo'")
    assert second.startswith("aviso: narração 'pt-br': regra auxiliar 'sobra'")


def test_verificar_reports_a_pack_warning_and_still_exits_0(tmp_path, campaign_data):
    campaign_data["narration_id"] = "meu"
    pack = builtin_pack_dict("pt-br") | {"id": "meu"}
    pack["rules"]["sobra"] = ["x"]
    (tmp_path / "narracoes").mkdir()
    (tmp_path / "narracoes" / "meu.json").write_text(json.dumps(pack), encoding="utf-8")
    path = tmp_path / "c.json"
    path.write_text(json.dumps(campaign_data), encoding="utf-8")
    result = run_verify(path)
    assert result.returncode == 0
    assert "aviso: narração 'meu': regra auxiliar 'sobra'" in result.stdout


# --- explain_validation_error: cada tipo de erro vira uma frase em português ------------


def explained(data):
    with pytest.raises(ValidationError) as caught:
        Campaign.model_validate(data)
    return dict(explain_validation_error(caught.value))


@pytest.fixture
def raw():
    return json.loads(CAMPAIGN_PATH.read_text(encoding="utf-8"))


def test_explain_missing_and_unknown_fields(raw):
    del raw["title"]
    raw["locations"][0]["inventado"] = 1
    out = explained(raw)
    assert out["title"] == "falta preencher 'title'"
    assert out["locations.0.inventado"] == "'inventado' não é um campo conhecido"


def test_explain_text_list_and_block_types(raw):
    raw["title"] = 3
    raw["locations"] = "nada"
    raw["npcs"][0] = 7
    out = explained(raw)
    assert out["title"] == "'title' precisa ser um texto"
    assert out["locations"] == "'locations' precisa ser uma lista"
    assert out["npcs.0"] == "item 1 de 'npcs' precisa ser um bloco de campos"


def test_explain_slug_pattern(raw):
    raw["id"] = "Com Espaço"
    out = explained(raw)
    assert "letras minúsculas sem acento" in out["id"]


def test_explain_unknown_condition_kind_has_no_variant_name_in_the_path(raw):
    raw["beats"][0]["activate_when"] = [{"kind": "invente"}]
    out = explained(raw)
    assert (
        out["beats.0.activate_when.0"] == "item 1 de 'activate_when': tipo de condição desconhecido"
    )


def test_explain_turn_at_least_number_type(raw):
    raw["beats"][0]["activate_when"] = [{"kind": "turn_at_least", "turn": "x"}]
    out = explained(raw)
    assert out["beats.0.activate_when.0.turn"] == "'turn' precisa ser um número inteiro"


def test_explain_list_items_name_the_list_and_the_position(raw):
    raw["locations"][0]["private_notes"] = ["ok", 3]
    raw["locations"][0]["connections"] = [5]
    out = explained(raw)
    assert out["locations.0.private_notes.1"] == "item 2 de 'private_notes' precisa ser um texto"
    assert out["locations.0.connections.0"] == "item 1 de 'connections' precisa ser um texto"


def test_the_condition_kinds_in_error_paths_come_from_the_schema():
    assert {
        "at_location",
        "npc_down",
        "beat_done",
        "turn_at_least",
        "check_passed",
    } == _CONDITION_KINDS


class _Limits(BaseModel):
    low: int = Field(ge=2)
    mode: Literal["a", "b"]
    day: date


def test_explain_minimum_choices_and_unknown_types():
    with pytest.raises(ValidationError) as caught:
        _Limits.model_validate({"low": 0, "mode": "z", "day": "x"})
    out = dict(explain_validation_error(caught.value))
    assert out["low"] == "'low' precisa ser pelo menos 2"
    assert out["mode"] == "'mode' tem um valor que não é aceito"
    # Tipo de erro que não conhecemos: frase genérica, com o que o Pydantic disse.
    assert out["day"].startswith("'day' não está certo (")


def test_explain_root_errors_have_no_quotes():
    with pytest.raises(ValidationError) as caught:
        _Limits.model_validate([])
    assert dict(explain_validation_error(caught.value)) == {
        "": "a campanha precisa ser um bloco de campos"
    }
