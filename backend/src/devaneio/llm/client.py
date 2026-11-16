"""Cliente mínimo para o formato OpenAI ``POST {base_url}/chat/completions``.

Só biblioteca padrão. Serve a qualquer servidor que fale esse formato (nuvem ou modelo
local). Quando ``json_mode`` está ligado, pede ``response_format: json_object``; se o
servidor recusar (HTTP 400/422, comum em servidores locais), repete sem o campo e deixa a
validação do JSON a cargo de quem chamou.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from .config import LlmConfig
from .errors import LlmError


class ChatClient(Protocol):
    """O que o jogo pede a um servidor de LLM: uma descrição e uma conclusão de conversa."""

    @property
    def description(self) -> str:
        """Modelo e servidor, para mostrar ao jogador."""
        ...

    def complete(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        json_mode: bool = False,
        temperature: float | None = None,
    ) -> str:
        """Envia as mensagens e devolve o texto da resposta; `LlmError` se falhar."""
        ...


class _HttpStatus(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(status, detail)
        self.status = status
        self.detail = detail


class OpenAiCompatClient:
    """Cliente para qualquer servidor no formato OpenAI chat/completions."""

    def __init__(self, config: LlmConfig, *, temperature: float = 0.7) -> None:
        self.config = config
        self.temperature = temperature

    @property
    def description(self) -> str:
        """Modelo e servidor, para mostrar ao jogador."""
        return self.config.description

    def complete(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        json_mode: bool = False,
        temperature: float | None = None,
    ) -> str:
        """Envia as mensagens e devolve o texto da resposta; `LlmError` se falhar."""
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [dict(m) for m in messages],
            "temperature": self.temperature if temperature is None else temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        try:
            try:
                return self._post(payload)
            except _HttpStatus as exc:
                if not (json_mode and exc.status in (400, 422)):
                    raise
                payload.pop("response_format")
                return self._post(payload)
        except _HttpStatus as exc:
            raise LlmError(f"o servidor respondeu HTTP {exc.status}: {exc.detail}") from None

    def _post(self, payload: dict[str, Any]) -> str:
        url = self.config.base_url.rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json", "User-Agent": "devaneio"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        # O esquema http(s) já foi validado em LlmConfig (config.py), antes de chegar aqui.
        request = urllib.request.Request(  # noqa: S310 — esquema http(s) validado em LlmConfig
            url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(  # noqa: S310 — esquema http(s) validado em LlmConfig
                request, timeout=self.config.timeout
            ) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raise _HttpStatus(exc.code, _snippet(exc)) from None
        except (urllib.error.URLError, OSError) as exc:  # inclui timeout
            reason = getattr(exc, "reason", exc)
            raise LlmError(f"falha de conexão com {self.config.host}: {reason}") from None

        try:
            content = json.loads(raw)["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            raise LlmError("resposta fora do formato chat/completions") from None
        if not isinstance(content, str) or not content.strip():
            raise LlmError("o modelo devolveu uma resposta vazia")
        return content


def _snippet(error: urllib.error.HTTPError) -> str:
    try:
        text = error.read().decode("utf-8", errors="replace")
    except OSError:
        text = ""
    return " ".join(text.split())[:200] or error.reason
