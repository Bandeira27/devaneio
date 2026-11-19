import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest

from devaneio.engine import advance_beats, reveal_facts
from devaneio.game import save_game
from devaneio.rules import RuleSystem, builtin_rules_json
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
    return json.loads(builtin_rules_json("default"))


@pytest.fixture
def rules(rules_data: dict):
    return RuleSystem.model_validate(rules_data)


@pytest.fixture(autouse=True)
def _no_llm_from_the_environment(monkeypatch):
    """Nenhum teste fala com um LLM real por causa das variáveis do usuário."""
    for name in ("BASE_URL", "MODEL", "API_KEY", "TIMEOUT"):
        monkeypatch.delenv(f"DEVANEIO_LLM_{name}", raising=False)


@pytest.fixture(autouse=True)
def opened_urls(monkeypatch):
    """Nenhum teste abre o navegador de verdade: os endereços que o servidor pediu para abrir ficam nesta lista."""
    urls: list[str] = []
    monkeypatch.setattr("webbrowser.open", lambda url, *_args, **_kwargs: urls.append(url) or True)
    return urls


def open_for_play(service, table_id):
    """Põe a mesa em andamento como ela nascia antes da sala de espera: com a abertura e sem o evento de início."""
    path = service.storage.path_for(table_id)
    with service.storage.lock(table_id):
        session = service.load_session(path)
        state, _ = advance_beats(session.state, session.campaign)
        state, _ = reveal_facts(state, session.campaign)
        table = session.table.model_copy(update={"phase": "running"})
        save_game(replace(session, state=state, table=table))
