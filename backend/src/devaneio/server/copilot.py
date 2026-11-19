"""Copiloto do anfitrião: o LLM assessora quem narra, só ele lê a resposta e nada muda no jogo.

Duas fases, sem gravação: (1) sob o lock da mesa, autentica e exige o anfitrião; (2) SEM o lock,
chama o LLM (pode levar minutos). Não há ``stale_revision``: a consulta só lê. A resposta volta
a quem perguntou e não passa por ``Presentation`` (mural e narração são de todos), não vira evento e
não é gravada; a pergunta também não. O contexto é a campanha inteira, segredos inclusive: o
anfitrião configurou o LLM e o aviso da mesa diz isso a todos.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

from devaneio.game import (
    CopilotContextTooLarge,
    LlmConfig,
    LlmError,
    Session,
    ask_copilot,
    clean_text,
    connect_llm,
)

from .errors import ApiFailure
from .llm_gate import COPILOT, require_llm, reserve
from .models import CopilotAnswer, CopilotRequest
from .storage import Storage
from .turns import authenticate

TABLE_KEY = "mesa"  # só o anfitrião consulta: o intervalo vale para a mesa, não por jogador


class CopilotDesk:
    """O balcão do copiloto: valida o pedido do anfitrião e chama o LLM fora do lock da mesa."""

    def __init__(
        self,
        storage: Storage,
        llm: Callable[[], LlmConfig | None],
        load: Callable[[Path], Session],
        cooldown: float,
    ) -> None:
        self._storage = storage
        self._llm = llm  # consultado a cada chamada: a tela de configuração o troca sem reiniciar
        self._cooldown = cooldown  # segundos entre duas consultas ao copiloto da mesa
        self._load = load  # carrega a partida; levanta o erro interno se ela estiver ilegível

    def run(self, table_id: str, path: Path, token: str, request: CopilotRequest) -> CopilotAnswer:
        """Responde uma pergunta do anfitrião; só ele vê a resposta."""
        storage = self._storage
        with storage.lock(table_id):  # fase 1
            session = self._load(path)
            _, _, player = authenticate(session, token)
            if player.role != "host":
                raise ApiFailure(403, "forbidden", "o copiloto é só do anfitrião")
        reserve(storage, table_id, COPILOT, TABLE_KEY, self._cooldown)
        try:  # fase 2, sem lock
            client = connect_llm(require_llm(self._llm))
            text = ask_copilot(client, session.campaign, session.rules, session.state, request.text)
        except CopilotContextTooLarge as exc:
            raise ApiFailure(
                422, "context_too_large", "a campanha é grande demais para o copiloto"
            ) from exc
        except LlmError as exc:
            print(
                f"llm: {clean_text(str(exc))}", file=sys.stderr
            )  # o detalhe fica com quem roda o servidor
            raise ApiFailure(
                502, "llm_unavailable", "o servidor de LLM não respondeu direito"
            ) from None
        finally:
            storage.leave_slot(table_id, COPILOT.kind)
        return CopilotAnswer(text=text)
