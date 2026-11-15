"""Servidor HTTP para jogar em grupo: uma mesa por partida, só biblioteca padrão.

Aqui só o serviço e os modelos; o adaptador HTTP fica em ``devaneio.server.http``, para
``export_schema`` ler ``server.models`` sem carregar ``http.server``.
"""

from .app import TableService
from .catalog import Catalog
from .errors import ApiFailure
from .storage import Storage

__all__ = ["ApiFailure", "Catalog", "Storage", "TableService"]
