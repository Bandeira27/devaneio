"""Configuração do LLM no editor: o que entra e o que sai das rotas ``/editor/settings/llm``.

A chave só entra (``LlmSettingsUpdate.api_key``) e nunca sai: a resposta diz apenas se existe uma
(``key_set``), sem trecho, tamanho nem máscara.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from devaneio.schema import StrictModel

MAX_URL = 300
MAX_MODEL = 200
MAX_KEY = 2000
MIN_TIMEOUT = 1.0
MAX_TIMEOUT = 600.0
DEFAULT_TIMEOUT = 60.0

LlmSource = Literal["screen", "environment", "none"]


class LlmSettingsView(StrictModel):
    """A configuração do LLM como o editor a mostra. Nunca traz a chave."""

    # De onde vem o LLM em uso: a tela, as variáveis de ambiente ou lugar nenhum (LLM desligado).
    source: LlmSource
    # `--sem-llm`: o servidor ignora qualquer configuração.
    disabled: bool
    # O que a tela guardou (vazio se nada foi salvo); o que vem do ambiente não aparece aqui.
    base_url: str | None
    model: str | None
    timeout: float | None
    key_set: bool
    # Modelo e servidor do LLM em uso, sem credencial (para o aviso de privacidade).
    description: str | None


class LlmSettingsUpdate(StrictModel):
    """A configuração a guardar. `api_key` ausente mantém a chave atual; não existe "enviar vazio"."""

    base_url: Annotated[str, Field(min_length=1, max_length=MAX_URL)]
    model: Annotated[str, Field(min_length=1, max_length=MAX_MODEL)]
    timeout: Annotated[float, Field(ge=MIN_TIMEOUT, le=MAX_TIMEOUT)] = DEFAULT_TIMEOUT
    api_key: Annotated[str, Field(min_length=1, max_length=MAX_KEY)] | None = None


class LlmTestResult(StrictModel):
    """O resultado de uma chamada curta ao LLM: `message` é sempre uma frase fixa, nunca o texto do servidor."""

    ok: bool
    message: str
