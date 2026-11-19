"""A ponte entre a mesa guardada no banco e a ``Session`` do jogo.

``game`` monta e desmonta partidas sem saber onde moram (``open_save``, ``build_save``); aqui o servidor as liga
ao banco (``Storage``) e à pasta de campanhas (``Catalog``). O estado e a mesa vão e voltam como JSON validado
pelos modelos do jogo; o ORM nunca vira modelo da API nem do motor.
"""

from __future__ import annotations

from pydantic import ValidationError

from devaneio.game import (
    ContentHashes,
    GameError,
    SaveFile,
    Session,
    TableMeta,
    build_save,
    open_save,
)
from devaneio.schema import GameState

from .catalog import Catalog
from .errors import ApiFailure
from .storage import Record, Scope, Storage


def record_from_save(data: SaveFile, reference: str) -> Record:
    """O que guardar de um ``SaveFile`` de mesa, com a campanha apontada por ``reference`` (relativo à pasta de campanhas).

    É o único lugar que desmonta um ``SaveFile`` em colunas: quem grava uma mesa e quem importa partidas passam por aqui.
    """
    if data.table is None:
        raise GameError("só mesa em grupo vai para o banco")
    return Record(
        campaign_path=reference,
        state=data.state.model_dump_json(),
        meta=data.table.model_dump_json(),
        content=None if data.content is None else data.content.model_dump_json(),
    )


class TableRecords:
    """Carrega e grava a ``Session`` de uma mesa: do banco para o jogo e de volta."""

    def __init__(self, storage: Storage, catalog: Catalog) -> None:
        self._storage = storage
        self._catalog = catalog

    def load(self, table_id: str, *, scope: Scope = "active") -> Session:
        """A partida de uma mesa. Registro ilegível é erro interno (``RuntimeError``, sem detalhe do dado).

        ``404`` se a mesa não existe (inclusive se foi apagada entre a checagem de quem chama e esta leitura).
        """
        record = self._storage.read(table_id, scope=scope)
        if record is None:
            raise ApiFailure(404, "table_not_found", "mesa não encontrada")
        try:
            campaign_path = self._catalog.inside(record.campaign_path)
            if campaign_path is None:
                raise GameError("a campanha sai da pasta permitida")
            data = SaveFile(
                campaign_path=record.campaign_path,
                state=GameState.model_validate_json(record.state),
                table=TableMeta.model_validate_json(record.meta),
                content=None
                if record.content is None
                else ContentHashes.model_validate_json(record.content),
            )
            return open_save(data, campaign_path, label=table_id)
        except (GameError, ValidationError, ValueError, OSError):
            # Sem ``from exc``: o traceback no log do servidor repetiria o dado (hashes e trechos do estado).
            raise RuntimeError(f"partida ilegível: {table_id}") from None

    def record_of(self, session: Session) -> Record:
        """O que guardar de uma partida de mesa: estado, mesa e conteúdo em JSON, e o caminho da campanha."""
        if session.table is None:
            raise GameError("só mesa em grupo vai para o banco")
        reference = self._catalog.relative(session.campaign_path)
        return record_from_save(build_save(session, reference), reference)

    def save(self, table_id: str, session: Session) -> None:
        """Regrava a mesa (``404`` se ela foi apagada no meio do caminho). Chamar com o lock dela tomado."""
        self._storage.save(table_id, self.record_of(session))

    def create(self, table_id: str, session: Session) -> bool:
        """Guarda uma mesa nova; ``False`` se o servidor já tem o máximo de mesas."""
        return self._storage.create(table_id, self.record_of(session))
