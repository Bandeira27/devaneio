import json
import subprocess
import sys

import pytest

from conftest import CAMPAIGN_PATH
from devaneio.game import check_content
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
