"""As mesas de uma campanha, vistas pelo editor: listar, encerrar e reemitir o acesso do anfitrião.

Só atende a própria máquina (as rotas ficam sob ``/editor/*``, que já recusa o resto). O servidor é a
fonte da verdade das mesas: o navegador guarda só o token de quem entrou, e perdê-lo não pode travar a
campanha nem a mesa. Nada aqui devolve segredo guardado (só hash existe em disco); o token e o convite
novos saem em claro uma única vez, na resposta de ``host_access``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from pydantic import ValidationError

from devaneio.game import GameError, load_game, save_game, saved_table_summary

from .auth import hash_secret, new_invite, new_token
from .catalog import Catalog
from .errors import ApiFailure
from .models import EditorTable, EditorTableClosed, HostAccess
from .storage import Storage


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
        self._token_source = token_source
        self._invite_source = invite_source

    def list_for(self, campaign_id: str) -> list[EditorTable]:
        """As mesas que usam a campanha, a mais recente primeiro. Mesa ilegível fica de fora."""
        campaign_path = self.catalog.path(campaign_id)
        if campaign_path is None:
            raise ApiFailure(404, "campaign_not_found", f"campanha '{campaign_id}' não existe")
        rows: list[EditorTable] = []
        for table_id in self.storage.table_ids():
            path = self.storage.path_for(table_id)
            found = saved_table_summary(path) if path is not None else None
            if path is None or found is None or found[0] != campaign_path.resolve():
                continue
            try:
                updated_at = path.stat().st_mtime
            except OSError:  # apagada entre o glob e a leitura
                continue
            table = found[1]
            host = next((p for p in table.players.values() if p.role == "host"), None)
            rows.append(
                EditorTable(
                    table_id=table_id,
                    phase=table.phase,
                    host_name=host.name if host else "",
                    players=len(table.players),
                    updated_at=updated_at,
                )
            )
        return sorted(rows, key=lambda row: row.updated_at, reverse=True)

    def close(self, table_id: str) -> EditorTableClosed:
        """Apaga o arquivo da mesa e acorda quem espera por ela (que recebe 404 na volta).

        Sob o lock da mesa, uma gravação em curso termina antes. A entrada em memória da mesa fica (alguns bytes até a
        próxima subida): quem espera compara a versão dela, e esquecê-la a faria voltar a zero e esconderia a mudança.
        """
        path = self.storage.path_for(table_id)
        if path is None:
            raise _not_found()
        with self.storage.lock(table_id):
            path.unlink(missing_ok=True)
            self.storage.announce_change(table_id)
        return EditorTableClosed(table_id=table_id)

    def host_access(self, table_id: str) -> HostAccess:
        """Um token e um convite novos para o anfitrião; os antigos deixam de valer.

        O servidor só guarda hash: nada se recupera, então reemite. Serve a quem perdeu o navegador que criou a mesa.
        """
        path = self.storage.path_for(table_id)
        if path is None:
            raise _not_found()
        with self.storage.lock(table_id):
            try:
                session = load_game(path, campaign_root=self.catalog.root)
            except (GameError, ValidationError, OSError):
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
            save_game(replace(session, table=table))
            self.storage.announce_change(table_id)
        return HostAccess(table_id=table_id, player_id=host_id, token=token, invite_code=invite)
