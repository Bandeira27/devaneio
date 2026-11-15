"""Serviço da mesa, sem HTTP além do status das falhas: cada operação carrega a partida do
arquivo dentro do lock da mesa, aplica a regra da mesa e grava. O arquivo é a fonte da
verdade; nada fica em memória: campanha e regras são relidas com a partida."""

from __future__ import annotations

import hmac
import time
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from pydantic import ValidationError

from devaneio.engine import game_status
from devaneio.game import (
    CommandError,
    GameError,
    GameOverError,
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
from .errors import ApiFailure
from .models import (
    TURN_POLICY,
    CampaignSummary,
    CampaignView,
    CommandRequest,
    CommandResult,
    CreateTableRequest,
    EventsView,
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
from .turns import apply, events_view

MAX_PLAYERS = 8

LLM_NOTICE = (
    "O texto enviado à mesa e o estado da partida (local, grupo, NPCs presentes com seus "
    "segredos, marcos ativos, eventos recentes) vão ao servidor de LLM configurado por quem "
    "roda esta mesa: {description}."
)


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

    def get_events(
        self, table_id: str, token: str | None, since: int, wait: float = 0
    ) -> EventsView:
        """Eventos de posição ``since`` em diante, com a prosa da gramática. Com ``wait`` > 0 e
        nada novo, espera até ``wait`` segundos por uma gravação da mesa (long-poll); acima de
        ``MAX_WAITERS`` esperas na mesa, responde de imediato."""
        # A versão vem ANTES da carga: uma gravação entre a carga e a espera deixaria a visão
        # velha com a versão nova, e o leitor dormiria com evento disponível. (Só com mesa
        # existente: ``version`` cria entrada, e o id ainda não foi validado.)
        seen = self.storage.version(table_id) if self.storage.path_for(table_id) else 0
        session, _, _ = self._open(table_id, token)
        view = EventsView(revision=len(session.state.events), events=events_view(session, since))
        if view.events or wait <= 0 or not self.storage.enter_wait(table_id):
            return view
        try:
            return self._wait_for_events(
                table_id, token, since=since, wait=wait, view=view, seen=seen
            )
        finally:
            self.storage.leave_wait(table_id)

    def _wait_for_events(
        self,
        table_id: str,
        token: str | None,
        *,
        since: int,
        wait: float,
        view: EventsView,
        seen: int,
    ) -> EventsView:
        deadline = time.monotonic() + wait
        changed = self.storage.condition(table_id)
        while not view.events:
            baseline = seen

            def moved(baseline: int = baseline) -> bool:
                return self.storage.version(table_id) != baseline

            with changed:  # o lock da mesa: wait() o solta enquanto espera
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not changed.wait_for(moved, remaining):
                    return view
                seen = self.storage.version(table_id)
            session, _, _ = self._open(table_id, token)
            view = EventsView(
                revision=len(session.state.events), events=events_view(session, since)
            )
        return view

    def run_command(
        self, table_id: str, token: str | None, request: CommandRequest
    ) -> CommandResult:
        """Um comando de um jogador: autentica, aplica a política da mesa (papel, dono do
        personagem, revisão, uma ação principal por personagem por turno), executa no motor
        e grava. Tudo dentro do lock da mesa; se qualquer passo recusa, nada é gravado."""
        path = self.storage.path_for(table_id)
        if path is None:
            raise ApiFailure(404, "table_not_found", "mesa não encontrada")
        if token is None:
            raise ApiFailure(401, "unauthorized", "token ausente")
        with self.storage.lock(table_id):
            session = self._load(path)
            table, player_id, player = self._authenticate(session, token)
            try:
                result, new_session, new_table = apply(session, table, player_id, player, request)
            except GameOverError as exc:
                raise ApiFailure(409, "game_over", str(exc)) from None
            except CommandError as exc:
                raise ApiFailure(422, "command_refused", str(exc)) from None
            if new_session.state is not session.state or new_table is not table:
                save_game(replace(new_session, table=new_table))
                self.storage.announce_change(table_id)
        return result

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
        table, _, player = self._authenticate(session, token)
        return session, table, player

    @staticmethod
    def _authenticate(session: Session, token: str) -> tuple[TableMeta, str, Player]:
        table = session.table
        if table is None:
            raise ApiFailure(404, "table_not_found", "mesa não encontrada")
        found = find_player(table, token)
        if found is None:
            raise ApiFailure(401, "unauthorized", "token inválido")
        return table, found[0], found[1]

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
