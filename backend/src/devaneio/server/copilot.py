"""Copiloto do anfitrião: o LLM assessora quem narra, só ele lê a resposta e nada muda no jogo.

Duas fases, sem gravação: (1) sob o lock da mesa, autentica e exige o anfitrião; (2) SEM o lock,
chama o LLM (pode levar minutos). Não há ``stale_revision``: a consulta só lê. A resposta volta
a quem perguntou e não passa por ``Presentation`` (mural e narração são de todos), não vira evento e
não é gravada; a pergunta também não. O contexto é a campanha inteira, segredos inclusive: o
anfitrião configurou o LLM e o aviso da mesa diz isso a todos.
"""

from __future__ import annotations

import math
import sys
from collections.abc import Callable
from pathlib import Path

from devaneio.game import LlmConfig, Session, connect_llm
from devaneio.llm import LlmError, ask_copilot

from .errors import ApiFailure
from .models import CopilotAnswer, CopilotRequest
from .storage import Storage
from .turns import authenticate


class CopilotDesk:
    def __init__(
        self,
        storage: Storage,
        llm: LlmConfig,
        load: Callable[[Path], Session],
        cooldown: float,
    ) -> None:
        self._storage = storage
        self._llm = llm
        self._cooldown = cooldown  # segundos entre duas consultas ao copiloto da mesa
        self._load = load  # carrega a partida; levanta o erro interno se ela estiver ilegível

    def run(self, table_id: str, path: Path, token: str, request: CopilotRequest) -> CopilotAnswer:
        storage = self._storage
        with storage.lock(table_id):  # fase 1
            session = self._load(path)
            _, _, player = authenticate(session, token)
            if player.role != "host":
                raise ApiFailure(403, "forbidden", "o copiloto é só do anfitrião")
        left = storage.copilot_cooldown_left(table_id, self._cooldown)
        if left > 0:
            raise ApiFailure(
                429, "copilot_rate_limited", f"espere {math.ceil(left)} s para consultar o copiloto"
            )
        if not storage.enter_copilot(table_id):
            raise ApiFailure(409, "copilot_busy", "já há uma consulta ao copiloto em andamento")
        storage.mark_copilot(table_id)  # conta mesmo se o LLM falhar
        try:  # fase 2, sem lock
            client = connect_llm(self._llm)
            text = ask_copilot(client, session.campaign, session.rules, session.state, request.text)
        except LlmError as exc:
            print(f"llm: {exc}", file=sys.stderr)  # o detalhe fica com quem roda o servidor
            raise ApiFailure(
                502, "llm_unavailable", "o servidor de LLM não respondeu direito"
            ) from None
        finally:
            storage.leave_copilot(table_id)
        return CopilotAnswer(text=text)
