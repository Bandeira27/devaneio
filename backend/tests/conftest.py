import copy
import json
from pathlib import Path

import pytest

from devaneio.schema import Campaign

CAMPAIGN_PATH = Path(__file__).resolve().parents[2] / "campaigns" / "sombra-do-vale.json"
# 3 locais, 1 facção, 2 NPCs (sacerdote com FOR 3 e PRE 4), 3 marcos encadeados.
_CAMPAIGN_DATA = json.loads(CAMPAIGN_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def campaign_data() -> dict:
    """Cópia fresca do dict da campanha, para o teste poder mutar à vontade."""
    return copy.deepcopy(_CAMPAIGN_DATA)


@pytest.fixture
def campaign(campaign_data: dict) -> Campaign:
    return Campaign.model_validate(campaign_data)


@pytest.fixture
def rules_data() -> dict:
    """Cópia fresca do sistema padrão como dict."""
    import json

    from devaneio.rules import builtin_rules_json

    return json.loads(builtin_rules_json("default"))


@pytest.fixture
def rules(rules_data: dict):
    from devaneio.rules import RuleSystem

    return RuleSystem.model_validate(rules_data)


@pytest.fixture(autouse=True)
def _no_llm_from_the_environment(monkeypatch):
    """Nenhum teste fala com um LLM real por causa das variáveis do usuário."""
    for name in ("BASE_URL", "MODEL", "API_KEY", "TIMEOUT"):
        monkeypatch.delenv(f"DEVANEIO_LLM_{name}", raising=False)
