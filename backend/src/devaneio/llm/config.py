"""Configuração do LLM, só por variáveis de ambiente.

A chave nunca é gravada em arquivo de partida, campanha ou repositório, e não aparece no
``repr``. O LLM é opcional: sem URL e modelo configurados, o jogo roda só com o motor.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from urllib.parse import urlparse

from .errors import LlmError

ENV_BASE_URL = "DEVANEIO_LLM_BASE_URL"
ENV_MODEL = "DEVANEIO_LLM_MODEL"
ENV_API_KEY = "DEVANEIO_LLM_API_KEY"
ENV_TIMEOUT = "DEVANEIO_LLM_TIMEOUT"


@dataclass(frozen=True)
class LlmConfig:
    base_url: str  # ex.: https://api.openai.com/v1 ou http://localhost:11434/v1
    model: str
    api_key: str | None = field(default=None, repr=False)
    timeout: float = 60.0

    @property
    def host(self) -> str:
        """``host[:porta]`` sem usuário e senha da URL: aparece em mensagens e avisos."""
        parsed = urlparse(self.base_url)
        port = f":{parsed.port}" if parsed.port else ""
        return f"{parsed.hostname or ''}{port}"

    @property
    def description(self) -> str:
        return f"{self.model} em {self.host}"

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> LlmConfig | None:
        """``None`` se URL base ou modelo faltam (LLM desligado). Valor malformado é erro."""
        base_url = env.get(ENV_BASE_URL, "").strip()
        model = env.get(ENV_MODEL, "").strip()
        if not base_url or not model:
            return None
        parsed = urlparse(base_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise LlmError(f"{ENV_BASE_URL} inválida: use http:// ou https:// com host")
        timeout = 60.0
        raw_timeout = env.get(ENV_TIMEOUT, "").strip()
        if raw_timeout:
            try:
                timeout = float(raw_timeout)
            except ValueError:
                raise LlmError(f"{ENV_TIMEOUT} inválido: {raw_timeout!r} não é número") from None
            if timeout <= 0:
                raise LlmError(f"{ENV_TIMEOUT} precisa ser positivo")
        api_key = env.get(ENV_API_KEY, "").strip() or None
        return cls(base_url=base_url, model=model, api_key=api_key, timeout=timeout)
