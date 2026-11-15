"""Serviço da mesa, sem HTTP além do status das falhas: cada operação carrega a partida do
arquivo dentro do lock da mesa, aplica a regra da mesa e grava. O arquivo é a fonte da
verdade; nada fica em memória: campanha e regras são relidas com a partida."""

from __future__ import annotations

import hmac
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
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
    execute,
    load_game,
    new_game,
    parse_line,
    save_game,
    split_actor,
)
from devaneio.llm import LlmConfig
from devaneio.schema import Campaign, GameState

from . import policy
from .auth import find_player, hash_secret, new_invite, new_token
from .catalog import Catalog
from .models import (
    MAX_NAME,
    TURN_POLICY,
    CampaignSummary,
    CampaignView,
    CommandRequest,
    CommandResult,
    CreateTableRequest,
    EventsView,
    EventView,
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
MAX_JOIN_ARGS = 30  # id, nome, atributos e itens do `entrar`

LLM_NOTICE = (
    "O texto enviado à mesa e o estado da partida (local, grupo, NPCs presentes com seus "
    "segredos, marcos ativos, eventos recentes) vão ao servidor de LLM configurado por quem "
    "roda esta mesa: {description}."
)


@dataclass(frozen=True)
class _Plan:
    """O que ``_authorize`` decidiu: o tipo do comando, o personagem que age (só em ações)
    e a linha final que o motor vai executar."""

    kind: policy.Kind | None
    actor: str
    line: str


def _prefixed(actor: str, rest: str) -> str:
    return f"{actor}: {rest}"


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
        view = EventsView(revision=len(session.state.events), events=self._events(session, since))
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
                revision=len(session.state.events), events=self._events(session, since)
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
                result, new_session, new_table = self._apply(
                    session, table, player_id, player, request
                )
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

    def _events(self, session: Session, since: int) -> list[EventView]:
        state = session.state
        return [
            EventView(
                index=index,
                turn=event.turn,
                kind=event.kind,
                text=event.text,
                prose=session.narrator.narrate(event, index, state),
            )
            for index, event in enumerate(state.events)
            if index >= since
        ]

    def _apply(
        self,
        session: Session,
        table: TableMeta,
        player_id: str,
        player: Player,
        request: CommandRequest,
    ) -> tuple[CommandResult, Session, TableMeta]:
        state = session.state
        plan = self._authorize(table, player, request, state)
        before = set(state.characters)
        new_session, text = execute(session, plan.line)
        new_table = table
        turn_ended = False
        if plan.kind == "action":
            new_table = table.model_copy(update={"acted": {**table.acted, plan.actor: state.turn}})
            new_session, text, turn_ended = self._close_turn_if_all_acted(
                new_session, new_table, text
            )
        elif plan.kind == "join":
            new_table = self._adopt(
                table, player_id, player, set(new_session.state.characters) - before
            )
        result = CommandResult(
            revision=len(new_session.state.events),
            events=self._events(new_session, len(state.events)),
            text=text,
            status=game_status(new_session.state),
            turn_ended=turn_ended,
        )
        return result, new_session, new_table

    def _authorize(
        self, table: TableMeta, player: Player, request: CommandRequest, state: GameState
    ) -> _Plan:
        """Decide se o jogador pode dar este comando agora e com qual linha final. Nada aqui
        muda a mesa; qualquer recusa levanta antes de ``execute``. Comando que o jogo não
        conhece (``kind`` ``None``) segue direto para o ``execute``, que o recusa com a
        mensagem de sempre."""
        actor, name, args = parse_line(request.line)
        kind = policy.classify(name)
        rest = split_actor(request.line)[1]
        line, who = request.line, ""

        if kind == "host" and player.role != "host":
            raise ApiFailure(403, "forbidden", f"'{name}' é um comando do anfitrião")
        if kind == "action":
            who = self._acting_character(player, actor)
            self._check_target(state, player, name, args)
            line = _prefixed(who, rest)
            if parse_line(line)[:2] != (who, name):  # a linha remontada diz o mesmo
                raise ApiFailure(400, "bad_request", "linha ambígua")
        elif kind == "join":
            self._check_join(state, player, args)
            line = rest
        elif kind == "read" and actor is None and player.character_ids:
            line = _prefixed(player.character_ids[0], rest)  # `ficha` sem id mostra a sua

        if kind in ("action", "join", "host") and request.revision != len(state.events):
            raise ApiFailure(
                409,
                "stale_revision",
                f"a mesa está na revisão {len(state.events)}, não em {request.revision}: releia",
            )
        if kind == "action" and table.acted.get(who) == state.turn:
            raise ApiFailure(409, "already_acted", f"'{who}' já agiu neste turno")
        return _Plan(kind, who, line)

    @staticmethod
    def _close_turn_if_all_acted(
        session: Session, table: TableMeta, text: str
    ) -> tuple[Session, str, bool]:
        if not policy.everyone_acted(table, session.state):
            return session, text, False
        try:
            closed, end_text = execute(session, "fim")
        except GameOverError:
            return session, text, False  # a ação acabou de encerrar a partida: sem turno a fechar
        return closed, f"{text}\n{end_text}", True

    @staticmethod
    def _adopt(table: TableMeta, player_id: str, player: Player, created: set[str]) -> TableMeta:
        """Liga o personagem recém-criado ao jogador que deu o ``entrar``."""
        [character_id] = created
        owner = player.model_copy(update={"character_ids": [*player.character_ids, character_id]})
        return table.model_copy(update={"players": {**table.players, player_id: owner}})

    @staticmethod
    def _acting_character(player: Player, named: str | None) -> str:
        """O personagem que age. Jogador comum: o seu (o único), nunca o de outro. Anfitrião:
        o que citar, ou o seu se tiver exatamente um. Nunca deixa o motor escolher sozinho,
        porque ``resolve_actor`` sem prefixo pega o único personagem da partida, de quem for."""
        if player.role == "host":
            if named is not None:
                return named
            if len(player.character_ids) == 1:
                return player.character_ids[0]
            raise ApiFailure(422, "actor_required", "diga qual personagem age: `id: comando`")
        if not player.character_ids:
            raise ApiFailure(403, "no_character", "você ainda não tem personagem: use `entrar`")
        if named is None:
            return player.character_ids[0]
        if named not in player.character_ids:
            raise ApiFailure(403, "forbidden", f"'{named}' não é um personagem seu")
        return named

    @staticmethod
    def _check_target(state: GameState, player: Player, name: str, args: list[str]) -> None:
        """Jogador comum só ataca quem vê: NPC de outro local responde como alvo inexistente,
        para o ataque não revelar nem ferir quem o ``olhar`` não mostra."""
        if name != "atacar" or player.role == "host" or len(args) < 2:
            return
        npc = state.npcs.get(args[1])
        if npc is not None and npc.location_id != state.current_location_id:
            raise ApiFailure(422, "command_refused", f"alvo '{args[1]}' não está na partida")

    @staticmethod
    def _check_join(state: GameState, player: Player, args: list[str]) -> None:
        if player.role != "host" and player.character_ids:
            raise ApiFailure(409, "character_limit", "você já tem um personagem")
        if len(args) > MAX_JOIN_ARGS or any(len(a) > MAX_NAME for a in args):
            raise ApiFailure(
                422,
                "command_refused",
                f"entrar aceita até {MAX_JOIN_ARGS} argumentos de até {MAX_NAME} caracteres",
            )
        if args and args[0] in state.npcs:
            raise ApiFailure(422, "command_refused", f"'{args[0]}' já é o id de um NPC")

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
