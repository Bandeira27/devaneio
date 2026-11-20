"""O chat da mesa: mensagens do grupo e sussurros, guardados no banco, fora do estado da partida.

``ChatStore`` fala com o banco; ``ChatDesk`` aplica a regra (quem pode escrever, em que fase, com que intervalo) e
acorda quem espera no long-poll. O motor, o ``game`` e o LLM não sabem que o chat existe (``docs/desenho-chat.md``).
"""

from __future__ import annotations

from collections.abc import Callable

from pydantic import ValidationError
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from devaneio.game import TableMeta

from .auth import find_player
from .database import Database
from .errors import ApiFailure
from .models import ChatMessageView, ChatRequest, ChatView
from .orm import ChatMessage
from .storage import Storage

MAX_STORED = 500  # mensagens guardadas por mesa; as mais antigas saem na gravação
PAGE = 100  # mensagens por leitura
COOLDOWN = 1.0  # segundos entre duas mensagens do mesmo jogador
SLOT = "chat"


def _view(row: ChatMessage, names: dict[str, str]) -> ChatMessageView:
    """A mensagem como a API a mostra; ``names`` resolve o nome do destinatário de um sussurro."""
    role = "host" if row.role == "host" else "player"
    return ChatMessageView(
        seq=row.seq,
        player_id=row.player_id,
        name=row.name,
        role=role,
        text=row.text,
        to=row.to_player_id,
        to_name=None if row.to_player_id is None else names.get(row.to_player_id),
        at=row.created_at,
    )


class ChatStore:
    """As mensagens do chat no banco, por mesa."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def add(
        self,
        table_id: str,
        *,
        player_id: str,
        to: str | None,
        name: str,
        role: str,
        text: str,
        at: float,
        names: dict[str, str],
    ) -> ChatMessageView:
        """Grava uma mensagem com o próximo ``seq`` da mesa e apaga as que passam do limite.

        Chamar com o lock da mesa tomado: ler o último ``seq`` e gravar o próximo é um passo só por mesa.
        """

        def write(session: Session) -> ChatMessageView:
            last = session.execute(
                select(func.max(ChatMessage.seq)).where(ChatMessage.table_id == table_id)
            ).scalar_one()
            row = ChatMessage(
                table_id=table_id,
                seq=(last or 0) + 1,
                player_id=player_id,
                to_player_id=to,
                name=name,
                role=role,
                text=text,
                created_at=at,
            )
            session.add(row)
            session.flush()
            session.execute(
                delete(ChatMessage).where(
                    ChatMessage.table_id == table_id, ChatMessage.seq <= row.seq - MAX_STORED
                )
            )
            return _view(row, names)

        return self._db.write(write)

    def since(self, table_id: str, since: int, viewer: str, names: dict[str, str]) -> ChatView:
        """Até ``PAGE`` mensagens que ``viewer`` pode ver, com ``seq`` > ``since``, em ordem.

        Vê a mensagem para a mesa toda e o sussurro que enviou ou recebeu; os dos outros, nunca. ``chat_seq`` é a última
        posição **da mesa** (sussurros alheios inclusive), para o cursor de quem lê não ficar parado.
        """

        def read(session: Session) -> ChatView:
            rows = (
                session.execute(
                    select(ChatMessage)
                    .where(
                        ChatMessage.table_id == table_id,
                        ChatMessage.seq > since,
                        or_(
                            ChatMessage.to_player_id.is_(None),
                            ChatMessage.to_player_id == viewer,
                            ChatMessage.player_id == viewer,
                        ),
                    )
                    .order_by(ChatMessage.seq.desc())
                    .limit(PAGE)
                )
                .scalars()
                .all()
            )
            last = session.execute(
                select(func.max(ChatMessage.seq)).where(ChatMessage.table_id == table_id)
            ).scalar_one()
            return ChatView(
                messages=[_view(row, names) for row in reversed(rows)], chat_seq=last or 0
            )

        return self._db.read(read)


def _names(table: TableMeta) -> dict[str, str]:
    return {player_id: player.name for player_id, player in table.players.items()}


class ChatDesk:
    """Enviar e ler o chat de uma mesa, com a regra da mesa."""

    def __init__(
        self, storage: Storage, clock: Callable[[], float], *, cooldown: float = COOLDOWN
    ) -> None:
        self._storage = storage
        self._store = ChatStore(storage.database)
        self._clock = clock
        self._cooldown = cooldown

    def _table(self, table_id: str) -> TableMeta:
        record = self._storage.read(table_id)
        if record is None:
            raise ApiFailure(404, "table_not_found", "mesa não encontrada")
        try:
            return TableMeta.model_validate_json(record.meta)
        except ValidationError:
            raise RuntimeError(f"mesa ilegível: {table_id}") from None

    def _who(self, table_id: str, token: str | None) -> tuple[TableMeta, str, str, str]:
        if token is None:
            raise ApiFailure(401, "unauthorized", "token ausente")
        table = self._table(table_id)
        found = find_player(table, token)
        if found is None:
            raise ApiFailure(401, "unauthorized", "token inválido")
        player_id, player = found
        return table, player_id, player.name, player.role

    def post(self, table_id: str, token: str | None, request: ChatRequest) -> ChatMessageView:
        """Envia uma mensagem à mesa toda ou, com ``to``, um sussurro a outro jogador. ``409 ended`` na mesa encerrada, ``429`` se escreve rápido demais."""
        if not self._storage.exists(table_id):
            raise ApiFailure(404, "table_not_found", "mesa não encontrada")
        with self._storage.lock(table_id):
            table, player_id, name, role = self._who(table_id, token)
            if request.to is not None and (
                request.to == player_id or request.to not in table.players
            ):
                raise ApiFailure(422, "bad_recipient", "o sussurro é para outro jogador desta mesa")
            if table.phase == "ended":
                raise ApiFailure(409, "ended", "a partida foi encerrada: o chat é só de leitura")
            wait = self._storage.slot_cooldown_left(table_id, SLOT, player_id, self._cooldown)
            if wait > 0:
                raise ApiFailure(
                    429,
                    "chat_rate_limited",
                    "devagar: espere um instante para mandar outra mensagem",
                )
            message = self._store.add(
                table_id,
                player_id=player_id,
                to=request.to,
                name=name,
                role=role,
                text=request.text,
                at=self._clock(),
                names=_names(table),
            )
            self._storage.mark_slot(table_id, SLOT, player_id)
            self._storage.announce_change(table_id)
        return message

    def read(self, table_id: str, token: str | None, since: int) -> ChatView:
        """As mensagens que o jogador pode ver (públicas e os sussurros dele) com ``seq`` > ``since``, até 100, em ordem."""
        table, player_id, _, _ = self._who(table_id, token)
        return self._store.since(table_id, since, player_id, _names(table))

    def since(self, table_id: str, since: int, viewer: str, table: TableMeta) -> ChatView:
        """O mesmo, sem autenticar: para quem já autenticou (o long-poll de ``get_events``)."""
        return self._store.since(table_id, since, viewer, _names(table))
