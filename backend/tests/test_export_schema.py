import json
import subprocess
import sys

import pytest

from devaneio.export_schema import DEFAULT_OUT, SCHEMAS, render

REGENERATE = "contract/ desatualizado: rode `python -m devaneio.export_schema`"


@pytest.mark.parametrize("name", list(SCHEMAS))
def test_committed_contract_matches_models(name):
    path = DEFAULT_OUT / name
    assert path.exists(), REGENERATE
    assert path.read_text(encoding="utf-8") == render(*SCHEMAS[name]), REGENERATE


def test_module_writes_every_schema(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "devaneio.export_schema", "--out", str(tmp_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "campaign.schema.json" in result.stdout
    campaign = json.loads((tmp_path / "campaign.schema.json").read_text(encoding="utf-8"))
    state = json.loads((tmp_path / "game_state.schema.json").read_text(encoding="utf-8"))
    assert campaign["title"] == "Campaign"
    assert state["title"] == "GameState"
    assert campaign["additionalProperties"] is False
    assert state["properties"]["state_version"]["const"] == 1
    # entrada: defaults opcionais; saída: tudo presente
    assert "locations" not in campaign["required"]
    assert "characters" in state["required"]
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(SCHEMAS)


def test_api_responses_never_carry_hashes():
    text = render(*SCHEMAS["api_responses.schema.json"])
    assert "token_hash" not in text
    assert "invite_hash" not in text
    assert "TableMeta" not in text
