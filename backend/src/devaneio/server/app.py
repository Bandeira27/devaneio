"""Serviço da mesa: cada operação da API, sem HTTP.

Só o status das falhas lembra HTTP. Cada operação carrega a partida do arquivo dentro do lock
da mesa, aplica a regra da mesa e grava. O arquivo é a fonte única da verdade
(campanha e regras são relidas com a partida); em memória ficam só a coordenação (locks, versão,
vagas de espera) e os parágrafos de narração do LLM, que são exibição descartável.
"""

from __future__ import annotations

import hmac
import sys
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import NamedTuple

from pydantic import ValidationError

from devaneio.engine import game_status
from devaneio.game import (
    CommandError,
    GameError,
    GameOverError,
    LlmConfig,
    Player,
    Role,
    Session,
    TableMeta,
    load_game,
    new_game,
    save_game,
)
from devaneio.schema import Campaign

from .auth import hash_secret, new_invite, new_token
from .catalog import Catalog
from .copilot import CopilotDesk
from .errors import ApiFailure
from .models import (
    TURN_POLICY,
    CampaignSummary,
    CampaignView,
    CommandRequest,
    CommandResult,
    CopilotAnswer,
    CopilotRequest,
    CreateTableRequest,
    EventsView,
    JoinRequest,
    LlmView,
    PlayerStateView,
    PlayerView,
    RulesView,
    SayRequest,
    SayResult,
    TableCreated,
    TableJoined,
    TableView,
    summarize,
)
from .say import SayDesk
from .storage import Storage
from .turns import apply, authenticate, events_view

MAX_PLAYERS = 8
SAY_COOLDOWN = 5.0  # segundos entre dois textos livres do mesmo jogador
HOST_ID = "p1"  # o anfitrião é sempre o primeiro jogador da mesa
COPILOT_COOLDOWN = 5.0  # segundos entre duas consultas ao copiloto da mesa


class Cursor(NamedTuple):
    """Até onde o cliente já leu a mesa.

    A posição do primeiro evento que ainda não viu e o ``seq`` da última fala que viu.
    """

    events: int
    talk: int


LLM_NOTICE = (
    "O texto enviado à mesa e o estado da partida (local, grupo, NPCs presentes{with_secrets}, "
    "marcos ativos, eventos que os jogadores veem) vão ao servidor de LLM configurado por quem "
    "roda esta mesa: {description}. {secrets_note}A fala e a narração que o LLM devolve voltam "
    "aos jogadores. O anfitrião também pode consultar um copiloto, que recebe a campanha inteira "
    "(segredos, fatos ocultos e notas privadas inclusive); a resposta dele volta só ao anfitrião."
)
NOTICE_WITH_SECRETS = (", segredos dos NPCs, fatos ocultos e notas privadas da campanha", "")
NOTICE_WITHOUT_SECRETS = ("", "Segredos, fatos ocultos e notas privadas não vão. ")


class TableService:
    """As operações da mesa em grupo (criar, entrar, comandar, ler), sem HTTP."""

    def __init__(
        self,
        catalog: Catalog,
        storage: Storage,
        *,
        llm: LlmConfig | None = None,
        say_cooldown: float = SAY_COOLDOWN,
        copilot_cooldown: float = COPILOT_COOLDOWN,
        llm_secrets: bool = False,
        token_source: Callable[[], str] = new_token,
        invite_source: Callable[[], str] = new_invite,
    ) -> None:
        self.catalog = catalog
        self.storage = storage
        self.llm = llm
        self._llm_secrets = llm_secrets
        self._warned: set[tuple[str, str]] = set()
        self._token_source = token_source
        self._invite_source = invite_source
        self._say = (
            SayDesk(storage, llm, self.load_session, say_cooldown, llm_secrets)
            if llm is not None
            else None
        )
        self._copilot = (
            CopilotDesk(storage, llm, self.load_session, copilot_cooldown)
            if llm is not None
            else None
        )

    # --- operações ---------------------------------------------------------------

    def list_campaigns(self) -> list[CampaignSummary]:
        """As campanhas do catálogo, só com título e premissa."""
        return self.catalog.summaries()

    def create_table(self, request: CreateTableRequest) -> TableCreated:
        """Cria uma mesa a partir de uma campanha do catálogo e devolve o token do anfitrião e o convite."""
        campaign_path = self.catalog.path(request.campaign_id)
        if campaign_path is None:
            raise ApiFailure(
                404, "campaign_not_found", f"campanha '{request.campaign_id}' não existe"
            )
        if self.storage.count() >= self.storage.max_tables:
            raise ApiFailure(409, "table_limit", "este servidor já tem o máximo de mesas")
        token, invite = self._token_source(), self._invite_source()
        host = Player(name=request.host_name, role="host", token_hash=hash_secret(token))
        table = TableMeta(invite_hash=hash_secret(invite), players={HOST_ID: host})
        table_id, save_path = self.storage.new_table_path()
        with self.storage.lock(table_id):
            session = replace(new_game(campaign_path, save_path, request.seed), table=table)
            save_game(session)
        return TableCreated(
            table_id=table_id,
            host_token=token,
            invite_code=invite,
            table=self._view(table_id, session, table, "host", HOST_ID),
        )

    def join_table(self, table_id: str, request: JoinRequest) -> TableJoined:
        """Entrada de um jogador por convite.

        Mesa inexistente e convite errado respondem igual (401), para o convite não servir
        de oráculo de existência; o limite de jogadores só vale depois.
        """
        path = self.storage.path_for(table_id)
        if path is None:
            raise ApiFailure(401, "invalid_invite", "convite inválido")
        with self.storage.lock(table_id):
            session = self.load_session(path)
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
            table=self._view(table_id, session, table, "player", player_id),
        )

    def get_events(
        self,
        table_id: str,
        token: str | None,
        since: int,
        *,
        wait: float = 0,
        since_talk: int = 0,
    ) -> EventsView:
        """Eventos e falas novos desde a última leitura, com espera opcional.

        Eventos de posição ``since`` em diante e falas com ``seq`` > ``since_talk``. Com
        ``wait`` > 0 e nada novo, espera até ``wait`` segundos por uma gravação da mesa
        (long-poll); acima de ``MAX_WAITERS`` esperas na mesa, responde de imediato.

        Com ``wait`` > 0 e sem ``since_talk``, o mural não conta como novidade: só falas
        posteriores a esta chamada acordam a espera (senão um cliente que não devolve
        ``talk_seq`` giraria sem esperar, relendo o arquivo a cada volta).
        """
        # Antes da carga: uma gravação entre as duas deixaria a visão velha com a versão nova.
        # Só com mesa existente, porque ``version`` cria entrada e o id ainda não foi validado.
        seen = self.storage.version(table_id) if self.storage.path_for(table_id) else 0
        cursor = Cursor(since, since_talk)
        view = self._events_view(table_id, token, cursor)
        if wait > 0 and since_talk == 0:
            cursor = Cursor(since, view.talk_seq)
            view = view.model_copy(update={"talk": []})
        if view.events or view.talk or wait <= 0 or not self.storage.enter_wait(table_id):
            return view
        try:
            return self._wait_for_events(table_id, token, cursor, wait=wait, view=view, seen=seen)
        finally:
            self.storage.leave_wait(table_id)

    def _events_view(self, table_id: str, token: str | None, cursor: Cursor) -> EventsView:
        session, _, _, player = self._open(table_id, token)
        presentation = self.storage.presentation(table_id)
        talk, talk_seq = presentation.talk_since(cursor.talk)
        return EventsView(
            revision=len(session.state.events),
            events=events_view(session, cursor.events, presentation.narrations(), role=player.role),
            talk=talk,
            talk_seq=talk_seq,
        )

    def _wait_for_events(
        self,
        table_id: str,
        token: str | None,
        cursor: Cursor,
        *,
        wait: float,
        view: EventsView,
        seen: int,
    ) -> EventsView:
        deadline = self.storage.now() + wait
        changed = self.storage.condition(table_id)
        while not (view.events or view.talk):
            baseline = seen

            def moved(baseline: int = baseline) -> bool:
                return self.storage.version(table_id) != baseline

            with changed:  # o lock da mesa: wait() o solta enquanto espera
                remaining = deadline - self.storage.now()
                if remaining <= 0 or not changed.wait_for(moved, remaining):
                    return view
                seen = self.storage.version(table_id)
            view = self._events_view(table_id, token, cursor)
        return view

    def run_command(
        self, table_id: str, token: str | None, request: CommandRequest
    ) -> CommandResult:
        """Executa um comando de um jogador.

        Autentica, aplica a política da mesa (papel, dono do personagem, revisão, uma ação
        principal por personagem por turno), executa no motor e grava. Tudo dentro do lock
        da mesa; se qualquer passo recusa, nada é gravado.
        """
        path = self.storage.path_for(table_id)
        if path is None:
            raise ApiFailure(404, "table_not_found", "mesa não encontrada")
        if token is None:
            raise ApiFailure(401, "unauthorized", "token ausente")
        with self.storage.lock(table_id):
            session = self.load_session(path)
            table, player_id, player = authenticate(session, token)
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

    def say(self, table_id: str, token: str | None, request: SayRequest) -> SayResult:
        """Texto livre pelo LLM do anfitrião (ver ``say.SayDesk``)."""
        if self._say is None:
            raise ApiFailure(409, "llm_disabled", "esta mesa não tem LLM configurado")
        path = self.storage.path_for(table_id)
        if path is None:
            raise ApiFailure(404, "table_not_found", "mesa não encontrada")
        if token is None:
            raise ApiFailure(401, "unauthorized", "token ausente")
        return self._say.run(table_id, path, token, request)

    def copilot(self, table_id: str, token: str | None, request: CopilotRequest) -> CopilotAnswer:
        """Consulta ao copiloto do anfitrião (ver ``copilot.CopilotDesk``)."""
        if self._copilot is None:
            raise ApiFailure(409, "llm_disabled", "esta mesa não tem LLM configurado")
        path = self.storage.path_for(table_id)
        if path is None:
            raise ApiFailure(404, "table_not_found", "mesa não encontrada")
        if token is None:
            raise ApiFailure(401, "unauthorized", "token ausente")
        return self._copilot.run(table_id, path, token, request)

    def get_table(self, table_id: str, token: str | None) -> TableView:
        """A mesa como o papel de quem pergunta pode ver."""
        session, table, player_id, player = self._open(table_id, token)
        return self._view(table_id, session, table, player.role, player_id)

    def get_campaign(self, table_id: str, token: str | None) -> Campaign | CampaignView:
        """A campanha como o papel de quem pergunta pode ver.

        A campanha inteira só para o anfitrião (o mestre); o jogador comum recebe a visão do
        que o ``olhar`` mostra, derivada do estado atual.
        """
        session, _, _, player = self._open(table_id, token)
        if player.role == "host":
            return session.campaign
        return CampaignView.of(session.campaign, session.state)

    def get_rules(self, table_id: str, token: str | None) -> RulesView:
        """O sistema de regras da mesa, para qualquer jogador.

        Alimenta os botões de ação e o formulário de personagem. Regra do sistema é dado público.
        """
        session, _, _, _ = self._open(table_id, token)
        return RulesView.of(session.rules)

    # --- apoio -------------------------------------------------------------------

    def _open(self, table_id: str, token: str | None) -> tuple[Session, TableMeta, str, Player]:
        """Carrega a mesa e autentica o jogador.

        404 e 401 saem daqui; partida ilegível é erro interno (a mensagem citaria caminho e
        trechos do arquivo). Limite conhecido: os hashes vivem no arquivo, então um token
        errado custa uma carga da partida.
        """
        path = self.storage.path_for(table_id)
        if path is None:
            raise ApiFailure(404, "table_not_found", "mesa não encontrada")
        if token is None:
            raise ApiFailure(401, "unauthorized", "token ausente")
        with self.storage.lock(table_id):
            session = self.load_session(path)
        table, player_id, player = authenticate(session, token)
        return session, table, player_id, player

    def load_session(self, path: Path) -> Session:
        """Carrega a partida de uma mesa; arquivo ilegível é erro interno, sem citar caminho."""
        try:
            session = load_game(path, campaign_root=self.catalog.root)
        except (GameError, ValidationError, OSError) as exc:
            raise RuntimeError(f"partida ilegível: {path.name}") from exc
        if not session.warnings:  # já salva com o conteúdo novo: um aviso futuro volta a valer
            self._warned = {w for w in self._warned if w[0] != path.name}
        for warning in session.warnings:
            if (path.name, warning) not in self._warned:  # uma vez por mesa, até salvar
                self._warned.add((path.name, warning))
                print(f"mesa {path.stem}: {warning}", file=sys.stderr)
        return session

    def _llm_view(self) -> LlmView:
        if self.llm is None:
            return LlmView(enabled=False)
        with_secrets, secrets_note = (
            NOTICE_WITH_SECRETS if self._llm_secrets else NOTICE_WITHOUT_SECRETS
        )
        return LlmView(
            enabled=True,
            description=self.llm.description,
            notice=LLM_NOTICE.format(
                description=self.llm.description,
                with_secrets=with_secrets,
                secrets_note=secrets_note,
            ),
            secrets=self._llm_secrets,
        )

    def _view(
        self, table_id: str, session: Session, table: TableMeta, role: Role, you: str
    ) -> TableView:
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
            you=you,
            state=state if role == "host" else PlayerStateView.of(state, session.rules),
        )
