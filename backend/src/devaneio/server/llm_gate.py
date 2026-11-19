"""Portão das chamadas de LLM da mesa: intervalo mínimo e uma chamada por vez, por tipo.

``say`` (texto livre dos jogadores) e ``copilot`` (consultas do anfitrião) custam chamadas ao LLM de quem
roda o servidor e usam o mesmo esqueleto: recusar se o intervalo não passou, recusar se já há uma em curso
e contar o pedido (mesmo que o LLM depois falhe). Cada tipo tem a sua vaga, e quem chama devolve a vaga
num ``finally`` com ``storage.leave_slot``.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

from devaneio.llm import LlmConfig

from .errors import ApiFailure
from .storage import Storage


@dataclass(frozen=True)
class LlmSlot:
    """Um tipo de chamada ao LLM (texto livre, copiloto) e as mensagens de recusa dele."""

    kind: str
    rate_code: str
    rate_text: str  # com {seconds}
    busy_code: str
    busy_text: str


SAY = LlmSlot(
    "say",
    "say_rate_limited",
    "espere {seconds} s para pedir outro texto livre",
    "say_busy",
    "já há uma ação de texto livre em andamento",
)
COPILOT = LlmSlot(
    "copilot",
    "copilot_rate_limited",
    "espere {seconds} s para consultar o copiloto",
    "copilot_busy",
    "já há uma consulta ao copiloto em andamento",
)


def require_llm(source: Callable[[], LlmConfig | None]) -> LlmConfig:
    """O LLM em uso agora; sem ele (nunca configurado, ou removido no meio do caminho), 409 ``llm_disabled``."""
    config = source()
    if config is None:
        raise ApiFailure(409, "llm_disabled", "esta mesa não tem LLM configurado")
    return config


def reserve(storage: Storage, table_id: str, slot: LlmSlot, key: str, cooldown: float) -> None:
    """Reserva a vaga de uma chamada ao LLM, respeitando o intervalo.

    ``ApiFailure`` 429 ou 409 se recusar (nada fica reservado). Depois de reservar, quem chama
    deve devolver a vaga num ``finally``.
    """
    left = storage.slot_cooldown_left(table_id, slot.kind, key, cooldown)
    if left > 0:
        raise ApiFailure(429, slot.rate_code, slot.rate_text.format(seconds=math.ceil(left)))
    if not storage.enter_slot(table_id, slot.kind):
        raise ApiFailure(409, slot.busy_code, slot.busy_text)
    storage.mark_slot(table_id, slot.kind, key)  # conta mesmo se o LLM falhar
