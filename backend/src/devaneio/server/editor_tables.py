"""As mesas de uma campanha, vistas pelo editor: listar, arquivar, restaurar, apagar de vez e reemitir o acesso do anfitrião.

Só atende a própria máquina (as rotas ficam sob ``/editor/*``, que já recusa o resto). Encerrar uma mesa é arquivá-la. O servidor é a
fonte da verdade das mesas: o navegador guarda só o token de quem entrou, e perdê-lo não pode travar a
campanha nem a mesa. Nada aqui devolve segredo guardado (só hash existe no banco); o token e o convite
novos saem em claro uma única vez, na resposta de ``host_access``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from pydantic import ValidationError

from devaneio.game import Phase, TableMeta
from devaneio.schema import GameState

from .auth import hash_secret, new_invite, new_token
from .catalog import Catalog
from .errors import ApiFailure
from .models import (
    ArchivedLog,
    ArchivedTable,
    EditorTable,
    EditorTableClosed,
    HostAccess,
    LogEvent,
)
from .records import TableRecords
from .storage import Storage


def _who(meta: str) -> tuple[Phase, str, int] | None:
    """A fase, o nome do anfitrião e quantos jogadores tem uma mesa, a partir da ``TableMeta`` em JSON; nada se ela não lê."""
    try:
        table = TableMeta.model_validate_json(meta)
    except ValidationError:
        return None
    host = next((p for p in table.players.values() if p.role == "host"), None)
    return table.phase, host.name if host else "", len(table.players)


def _not_found() -> ApiFailure:
    return ApiFailure(404, "table_not_found", "essa mesa não existe neste servidor")


class EditorTables:
    """As três operações do editor sobre as mesas, sem HTTP."""

    def __init__(
        self,
        catalog: Catalog,
        storage: Storage,
        *,
        token_source: Callable[[], str] = new_token,
        invite_source: Callable[[], str] = new_invite,
    ) -> None:
        self.catalog = catalog
        self.storage = storage
        self._records = TableRecords(storage, catalog)
        self._token_source = token_source
        self._invite_source = invite_source

    def list_for(self, campaign_id: str) -> list[EditorTable]:
        """As mesas que usam a campanha, a mais recente primeiro. Mesa ilegível fica de fora."""
        campaign_path = self.catalog.path(campaign_id)
        if campaign_path is None:
            raise ApiFailure(404, "campaign_not_found", f"campanha '{campaign_id}' não existe")
        rows: list[EditorTable] = []
        for summary in self.storage.summaries(self.catalog.relative(campaign_path)):
            who = _who(summary.meta)
            if who is not None:
                phase, host_name, players = who
                rows.append(
                    EditorTable(
                        table_id=summary.table_id,
                        phase=phase,
                        host_name=host_name,
                        players=players,
                        updated_at=summary.updated_at,
                    )
                )
        return sorted(rows, key=lambda row: row.updated_at, reverse=True)

    def archive(self, table_id: str) -> EditorTableClosed:
        """Arquiva a mesa e acorda quem espera por ela (que recebe 404 na volta). O estado e o log ficam.

        Sob o lock da mesa, uma gravação em curso termina antes. A entrada em memória da mesa fica (alguns bytes até a
        próxima subida): quem espera compara a versão dela, e esquecê-la a faria voltar a zero e esconderia a mudança.
        """
        if not self.storage.exists(table_id):
            raise _not_found()
        with self.storage.lock(table_id):
            if not self.storage.archive(table_id):  # arquivada ou apagada entre a checagem e o lock
                raise _not_found()
            self.storage.announce_change(table_id)
        return EditorTableClosed(table_id=table_id)

    def list_archived(self, campaign_id: str) -> list[ArchivedTable]:
        """As mesas arquivadas da campanha, a mais recente primeiro. Mesa ilegível fica de fora."""
        campaign_path = self.catalog.path(campaign_id)
        if campaign_path is None:
            raise ApiFailure(404, "campaign_not_found", f"campanha '{campaign_id}' não existe")
        rows: list[ArchivedTable] = []
        for summary in self.storage.summaries(
            self.catalog.relative(campaign_path), scope="archived"
        ):
            who = _who(summary.meta)
            if who is not None:
                phase, host_name, players = who
                rows.append(
                    ArchivedTable(
                        table_id=summary.table_id,
                        phase=phase,
                        host_name=host_name,
                        players=players,
                        updated_at=summary.updated_at,
                        archived_at=summary.archived_at or 0.0,
                    )
                )
        return sorted(rows, key=lambda row: row.archived_at, reverse=True)

    def restore(self, table_id: str) -> EditorTable:
        """Traz de volta uma mesa arquivada, se a partida ainda combina com a campanha e há vaga entre as mesas ativas.

        Os tokens e o convite de antes voltam a valer. A partida é conferida **antes** de restaurar: se a campanha mudou
        a ponto de ela não abrir, a mesa segue arquivada, com a data original, e a resposta é ``409 table_unreadable``.
        """
        if not self.storage.exists(
            table_id, scope="archived"
        ):  # antes do lock: id inventado não cria entrada
            raise _not_found()
        with self.storage.lock(table_id):
            try:
                self._records.load(table_id, scope="archived")
            except ApiFailure:  # apagada ou restaurada entre a checagem e o lock
                raise _not_found() from None
            except RuntimeError:
                raise ApiFailure(
                    409,
                    "table_unreadable",
                    "a partida não combina mais com a campanha: ela segue arquivada",
                ) from None
            if not self.storage.restore(table_id):  # 409 table_limit sobe daqui
                raise _not_found()
            self.storage.announce_change(table_id)
        record = self.storage.read(table_id)
        who = _who(record.meta) if record is not None else None
        if who is None:  # a mesa já foi restaurada; só não dá para descrevê-la
            raise ApiFailure(409, "table_unreadable", "não consegui ler essa mesa")
        phase, host_name, players = who
        return EditorTable(
            table_id=table_id,
            phase=phase,
            host_name=host_name,
            players=players,
            updated_at=self.storage.updated_at(table_id),
        )

    def purge(self, table_id: str) -> EditorTableClosed:
        """Apaga de vez uma mesa arquivada: o estado e o log vão junto. Só a arquivada; não tem volta."""
        if not self.storage.exists(
            table_id, scope="archived"
        ):  # antes do lock: id inventado não cria entrada
            raise _not_found()
        with self.storage.lock(table_id):
            if not self.storage.delete(table_id):
                raise _not_found()
        return EditorTableClosed(table_id=table_id)

    def history(self, table_id: str) -> ArchivedLog:
        """O log inteiro de uma mesa arquivada, em ordem. Só texto: nem os dados dos eventos, nem hash, nem convite."""
        record = self.storage.read(table_id, scope="archived")
        if record is None:
            raise _not_found()
        try:
            state = GameState.model_validate_json(record.state)
        except ValidationError:
            raise ApiFailure(409, "table_unreadable", "não consegui ler essa mesa") from None
        return ArchivedLog(
            table_id=table_id,
            turn=state.turn,
            events=[
                LogEvent(index=i, turn=e.turn, kind=e.kind, text=e.text)
                for i, e in enumerate(state.events)
            ],
        )

    def host_access(self, table_id: str) -> HostAccess:
        """Um token e um convite novos para o anfitrião; os antigos deixam de valer.

        O servidor só guarda hash: nada se recupera, então reemite. Serve a quem perdeu o navegador que criou a mesa.
        """
        if not self.storage.exists(table_id):
            raise _not_found()
        with self.storage.lock(table_id):
            if not self.storage.exists(table_id):  # apagada entre a checagem e o lock
                raise _not_found()
            try:
                session = self._records.load(table_id)
            except RuntimeError:
                raise ApiFailure(409, "table_unreadable", "não consegui ler essa mesa") from None
            table = session.table
            host_id = (
                next((pid for pid, p in table.players.items() if p.role == "host"), None)
                if table is not None
                else None
            )
            if table is None or host_id is None:
                raise ApiFailure(409, "table_unreadable", "essa mesa não tem anfitrião")
            token, invite = self._token_source(), self._invite_source()
            host = table.players[host_id].model_copy(update={"token_hash": hash_secret(token)})
            table = table.model_copy(
                update={
                    "invite_hash": hash_secret(invite),
                    "players": {**table.players, host_id: host},
                }
            )
            self._records.save(table_id, replace(session, table=table))
            self.storage.announce_change(table_id)
        return HostAccess(table_id=table_id, player_id=host_id, token=token, invite_code=invite)
