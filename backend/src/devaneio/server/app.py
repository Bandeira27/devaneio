"""Serviço da mesa, sem HTTP além do status das falhas: cada operação carrega a partida do
arquivo dentro do lock da mesa, aplica a regra da mesa e grava. O arquivo é a fonte da
verdade; nada fica em memória: campanha e regras são relidas com a partida."""

from __future__ import annotations

import hmac
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from pydantic import ValidationError

from devaneio.engine import game_status
from devaneio.game import (
    GameError,
    Player,
    Role,
    Session,
    TableMeta,
    load_game,
    new_game,
    save_game,
)
from devaneio.llm import LlmConfig
from devaneio.schema import Campaign

from .auth import find_player, hash_secret, new_invite, new_token
from .catalog import Catalog
from .models import (
    TURN_POLICY,
    CampaignSummary,
    CampaignView,
    CreateTableRequest,
    JoinRequest,
    LlmView,
    PlayerStateView,
    PlayerView,
    TableCreated,
    TableJoined,
    TableView,
    summarize,
)
from .storage import Storage

MAX_PLAYERS = 8

LLM_NOTICE = (
    "O texto enviado à mesa e o estado da partida (local, grupo, NPCs presentes com seus "
    "segredos, marcos ativos, eventos recentes) vão ao servidor de LLM configurado por quem "
    "roda esta mesa: {description}."
)


class ApiFailure(Exception):
    """Falha com status HTTP definido e mensagem que pode ir ao cliente."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class TableService:
    def __init__(
        self,
        catalog: Catalog,
        storage: Storage,
        *,
        llm: LlmConfig | None = None,
        token_source: Callable[[], str] = new_token,
        invite_source: Callable[[], str] = new_invite,
    ) -> None:
        self.catalog = catalog
        self.storage = storage
        self.llm = llm
        self._token_source = token_source
        self._invite_source = invite_source

    # --- operações ---------------------------------------------------------------

    def list_campaigns(self) -> list[CampaignSummary]:
        return self.catalog.summaries()

    def create_table(self, request: CreateTableRequest) -> TableCreated:
        campaign_path = self.catalog.path(request.campaign_id)
        if campaign_path is None:
            raise ApiFailure(
                404, "campaign_not_found", f"campanha '{request.campaign_id}' não existe"
            )
        if self.storage.count() >= self.storage.max_tables:
            raise ApiFailure(409, "table_limit", "este servidor já tem o máximo de mesas")
        token, invite = self._token_source(), self._invite_source()
        host = Player(name=request.host_name, role="host", token_hash=hash_secret(token))
        table = TableMeta(invite_hash=hash_secret(invite), players={"p1": host})
        table_id, save_path = self.storage.new_table_path()
        with self.storage.lock(table_id):
            session = replace(new_game(campaign_path, save_path, request.seed), table=table)
            save_game(session)
        return TableCreated(
            table_id=table_id,
            host_token=token,
            invite_code=invite,
            table=self._view(table_id, session, table, "host"),
        )

    def join_table(self, table_id: str, request: JoinRequest) -> TableJoined:
        """Entrada por convite. Mesa inexistente e convite errado respondem igual (401), para
        o convite não servir de oráculo de existência; o limite de jogadores só vale depois."""
        path = self.storage.path_for(table_id)
        if path is None:
            raise ApiFailure(401, "invalid_invite", "convite inválido")
        with self.storage.lock(table_id):
            session = self._load(path)
            table = session.table
            if table is None or not hmac.compare_digest(
                hash_secret(request.invite_code), table.invite_hash
            ):
                raise ApiFailure(401, "invalid_invite", "convite inválido")
            if len(table.players) >= MAX_PLAYERS:
                raise ApiFailure(409, "table_full", f"a mesa já tem {MAX_PLAYERS} jogadores")
            if request.name.casefold() in {p.name.casefold() for p in table.players.values()}:
                raise ApiFailure(
                    409, "name_taken", f"já existe um jogador chamado '{request.name}'"
                )
            token = self._token_source()
            player_id = f"p{len(table.players) + 1}"
            player = Player(name=request.name, role="player", token_hash=hash_secret(token))
            table = table.model_copy(update={"players": {**table.players, player_id: player}})
            session = replace(session, table=table)
            save_game(session)
        return TableJoined(
            player_id=player_id,
            token=token,
            table=self._view(table_id, session, table, "player"),
        )

    def get_table(self, table_id: str, token: str | None) -> TableView:
        session, table, player = self._open(table_id, token)
        return self._view(table_id, session, table, player.role)

    def get_campaign(self, table_id: str, token: str | None) -> Campaign | CampaignView:
        """A campanha inteira só para o anfitrião (o mestre); o jogador comum recebe a visão
        do que o ``olhar`` mostra, derivada do estado atual."""
        session, _, player = self._open(table_id, token)
        if player.role == "host":
            return session.campaign
        return CampaignView.of(session.campaign, session.state)

    # --- apoio -------------------------------------------------------------------

    def _open(self, table_id: str, token: str | None) -> tuple[Session, TableMeta, Player]:
        """Carrega a mesa e autentica o jogador. 404 e 401 saem daqui; partida ilegível
        é erro interno (a mensagem citaria caminho e trechos do arquivo). Limite conhecido:
        os hashes vivem no arquivo, então um token errado custa uma carga da partida."""
        path = self.storage.path_for(table_id)
        if path is None:
            raise ApiFailure(404, "table_not_found", "mesa não encontrada")
        if token is None:
            raise ApiFailure(401, "unauthorized", "token ausente")
        with self.storage.lock(table_id):
            session = self._load(path)
        if session.table is None:
            raise ApiFailure(404, "table_not_found", "mesa não encontrada")
        found = find_player(session.table, token)
        if found is None:
            raise ApiFailure(401, "unauthorized", "token inválido")
        return session, session.table, found[1]

    def _load(self, path: Path) -> Session:
        try:
            return load_game(path, campaign_root=self.catalog.root)
        except (GameError, ValidationError, OSError) as exc:
            raise RuntimeError(f"partida ilegível: {path.name}") from exc

    def _llm_view(self) -> LlmView:
        if self.llm is None:
            return LlmView(enabled=False)
        return LlmView(
            enabled=True,
            description=self.llm.description,
            notice=LLM_NOTICE.format(description=self.llm.description),
        )

    def _view(self, table_id: str, session: Session, table: TableMeta, role: Role) -> TableView:
        state = session.state
        return TableView(
            table_id=table_id,
            role=role,
            campaign=summarize(session.campaign),
            players=[
                PlayerView(id=pid, name=p.name, role=p.role, character_ids=list(p.character_ids))
                for pid, p in table.players.items()
            ],
            turn_policy=TURN_POLICY,
            acted=dict(table.acted),
            revision=len(session.state.events),
            status=game_status(session.state),
            llm=self._llm_view(),
            state=state if role == "host" else PlayerStateView.of(state, session.rules),
        )
