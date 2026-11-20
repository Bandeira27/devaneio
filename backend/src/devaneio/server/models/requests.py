"""Entrada da API: limites, sanitização de nomes e linhas, e os corpos das requisições."""

from __future__ import annotations

import unicodedata
from typing import Annotated, Literal

from pydantic import BeforeValidator, Field

from devaneio.schema import (
    Id,
    StrictModel,
)

MAX_NAME = 40


MAX_SEED = 2**53  # mesma faixa portável de new_game


_FORBIDDEN_CATEGORIES = {"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"}


def clean_name(value: object) -> object:
    """Limpa um nome de jogador.

    NFKC, sem caracteres de controle, formatação ou separadores de linha (ANSI, zero-width,
    bidi), espaços colapsados. Sem isso, "Ana\u200b" passaria por outro jogador e o nome chegaria
    sujo ao log, ao prompt do LLM e à tela dos outros.
    """
    if not isinstance(value, str):
        return value
    text = unicodedata.normalize("NFKC", value)
    if any(unicodedata.category(ch) in _FORBIDDEN_CATEGORIES for ch in text):
        raise ValueError("o nome não pode ter caracteres de controle ou invisíveis")
    return " ".join(text.split())


PlayerName = Annotated[str, BeforeValidator(clean_name), Field(min_length=1, max_length=MAX_NAME)]

MAX_INVITE = 64
InviteCode = Annotated[
    str, Field(min_length=1, max_length=MAX_INVITE)
]  # o formato do convite, num lugar só


def clean_line(value: object) -> object:
    """Limpa uma linha de comando.

    Mesma regra dos nomes quanto a caracteres de controle e invisíveis (um nome de personagem
    entre aspas viraria ANSI ou bidi na tela dos outros), sem colapsar espaços, que podem estar
    entre aspas.
    """
    if not isinstance(value, str):
        return value
    text = unicodedata.normalize("NFKC", value).strip()
    if any(unicodedata.category(ch) in _FORBIDDEN_CATEGORIES for ch in text):
        raise ValueError("a linha não pode ter caracteres de controle ou invisíveis")
    return text


MAX_LINE = 500


CommandLine = Annotated[str, BeforeValidator(clean_line), Field(min_length=1, max_length=MAX_LINE)]


class CreateTableRequest(StrictModel):
    """Criar uma mesa: a campanha, o nome do anfitrião e, opcionalmente, a semente."""

    campaign_id: Id
    host_name: PlayerName
    seed: int | None = Field(default=None, ge=0, lt=MAX_SEED)


class JoinRequest(StrictModel):
    """Entrar numa mesa: o código de convite e o nome."""

    invite_code: InviteCode
    name: PlayerName


class InvitePreviewRequest(StrictModel):
    """Espiar para onde um convite leva: só o código de convite."""

    invite_code: InviteCode


class CommandRequest(StrictModel):
    """Um comando: a linha e a revisão da mesa que o cliente viu."""

    line: CommandLine
    # Número de eventos que o cliente viu: comando que muda a partida com revisão velha é recusado.
    revision: int = Field(ge=0)


class LifecycleRequest(StrictModel):
    """Uma mudança de fase da mesa, pedida pelo anfitrião: iniciar, pausar, retomar ou encerrar."""

    action: Literal["start", "pause", "resume", "end"]
    # Número de eventos que o cliente viu: mudar a fase com a mesa andada (um comando no meio) é recusado.
    revision: int = Field(ge=0)


MAX_CHAT = 500
ChatText = Annotated[str, BeforeValidator(clean_line), Field(min_length=1, max_length=MAX_CHAT)]


class ChatRequest(StrictModel):
    """Uma mensagem para o chat da mesa: uma linha de texto, para o grupo todo ou, com ``to``, um sussurro para um jogador."""

    text: ChatText
    # O id do jogador que recebe um sussurro; ausente = mensagem para a mesa toda.
    to: Id | None = None


class SayRequest(StrictModel):
    """Um texto livre para o mestre de IA: o texto e a revisão que o cliente viu."""

    text: CommandLine
    revision: int = Field(ge=0)


class CopilotRequest(StrictModel):
    """Pergunta avulsa ao copiloto do anfitrião (sem estado: cada chamada leva o contexto atual)."""

    text: CommandLine
