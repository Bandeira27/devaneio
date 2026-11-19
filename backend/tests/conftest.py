import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import update

from devaneio.engine import advance_beats, reveal_facts
from devaneio.rules import RuleSystem, builtin_rules_json
from devaneio.schema import Campaign
from devaneio.server import Storage
from devaneio.server.database import DB_NAME, Database
from devaneio.server.files import prepare_data_dir
from devaneio.server.migrations import migrate
from devaneio.server.orm import GameTable

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
    with service.storage.lock(table_id):
        session = service.load_session(table_id)
        state, _ = advance_beats(session.state, session.campaign)
        state, _ = reveal_facts(state, session.campaign)
        table = session.table.model_copy(update={"phase": "running"})
        service._records.save(table_id, replace(session, state=state, table=table))


def make_storage(folder, **kwargs):
    """Um ``Storage`` sobre um banco novo (com as migrações) na pasta dada, como o servidor monta."""
    database = Database(prepare_data_dir(folder) / DB_NAME)
    migrate(database)
    return Storage(database, **kwargs)


def table_text(service, table_id) -> str:
    """Tudo o que está guardado da mesa, em texto (estado, mesa e conteúdo): para procurar o que não pode estar lá."""
    record = service.storage.read(table_id)
    return "\n".join(part for part in (record.state, record.meta, record.content) if part)


def save_session(service, table_id, session) -> None:
    """Grava a partida na mesa, como o servidor faz depois de uma ação."""
    with service.storage.lock(table_id):
        service._records.save(table_id, session)


def corrupt(service, table_id, **columns) -> None:
    """Estraga colunas da mesa guardada (``state``, ``meta``, ``campaign_path``), para provar o que o servidor faz com dado ruim."""

    def write(session):
        session.execute(update(GameTable).where(GameTable.id == table_id).values(**columns))

    service.storage._db.write(write)
