"""A configuração do LLM da máquina: URL, modelo e tempo no banco; a chave num arquivo à parte.

A chave **não** mora no banco: cópia, backup e exportação do ``.db`` não podem levá-la. Ela fica em
``<dados>/llm.key``, criado já com ``0600`` (nunca com permissão aberta, nem por um instante) e trocado de
forma atômica. Nada aqui devolve a chave, inteira ou em parte, nem a escreve em log ou mensagem de erro.

Precedência do LLM em uso, **sem misturar**: o que a tela guardou (URL e modelo) vale por inteiro, com a
chave do arquivo; sem isso, a configuração do ambiente (``DEVANEIO_LLM_*``) por inteira; sem nenhuma,
LLM desligado. ``--sem-llm`` desliga tudo. A chave do ambiente nunca vai para uma URL que veio da tela.
"""

from __future__ import annotations

import os
import re
import sys
import threading
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from devaneio.game import connect_llm
from devaneio.llm import LlmConfig, LlmError

from .database import Database
from .errors import ApiFailure, DatabaseError
from .files import tighten
from .models.settings import (
    LlmSettingsUpdate,
    LlmSettingsView,
    LlmSource,
    LlmTestResult,
)
from .orm import Setting

KEY_FILE = "llm.key"
KEY_BASE_URL = "llm.base_url"
KEY_MODEL = "llm.model"
KEY_TIMEOUT = "llm.timeout"
SCREEN_KEYS = (KEY_BASE_URL, KEY_MODEL, KEY_TIMEOUT)
HTTP_STATUS = re.compile(r"HTTP (\d{3})")
TEST_PROMPT = [{"role": "user", "content": "Responda apenas com a palavra: ok"}]


def _invalid(message: str) -> ApiFailure:
    return ApiFailure(422, "invalid_settings", message)


def validate_update(update: LlmSettingsUpdate) -> None:
    """Recusa o que não pode virar configuração (``ApiFailure`` 422, mensagem sem eco da chave)."""
    parsed = urlparse(update.base_url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise _invalid("o endereço precisa começar com http:// ou https:// e ter um servidor")
    if parsed.username is not None or parsed.password is not None:
        raise _invalid("o endereço não pode ter usuário e senha: a chave vai no campo próprio")
    if parsed.query or parsed.fragment:
        raise _invalid("o endereço não pode ter parâmetros nem âncora")
    try:
        parsed.port  # noqa: B018 — acessar valida o número da porta
    except ValueError:
        raise _invalid("a porta do endereço é inválida") from None
    if not update.model.strip():
        raise _invalid("o modelo não pode ficar em branco")
    key = update.api_key
    if key is not None and not (
        key.isascii() and key.isprintable() and not any(ch.isspace() for ch in key)
    ):
        # Vai num cabeçalho HTTP: só ASCII visível (acentos e outros alfabetos quebrariam o envio).
        raise _invalid("a chave só pode ter letras, números e símbolos ASCII, sem espaços")


def _origin(url: str) -> tuple[str, str, int | None]:
    """Esquema, servidor e porta de um endereço: o que identifica *para quem* a chave é enviada."""
    parsed = urlparse(url)
    default = 443 if parsed.scheme == "https" else 80
    return parsed.scheme, (parsed.hostname or "").lower(), parsed.port or default


class SettingsStore:
    """Lê e grava a configuração do LLM e diz qual vale agora."""

    def __init__(
        self,
        db: Database,
        data_dir: Path,
        *,
        environment: LlmConfig | None = None,
        disabled: bool = False,
    ) -> None:
        self._db = db
        self._key_path = Path(data_dir).resolve() / KEY_FILE
        self._environment = environment
        self._disabled = disabled
        self._lock = threading.Lock()  # protege o cache, a geração dele e a troca da chave
        self._cached: tuple[LlmConfig | None, LlmSource] | None = None
        self._generation = 0  # sobe a cada mudança: um cálculo feito antes dela não vira cache

    # --- o que vale agora --------------------------------------------------------

    def effective(self) -> LlmConfig | None:
        """O LLM em uso, ou ``None``. Lê do cache: só muda quando a tela salva ou remove."""
        return self._resolve()[0]

    def view(self) -> LlmSettingsView:
        """O estado da configuração para o editor, sem a chave. Tudo sai de uma só leitura do banco."""
        screen = self._read_screen()
        config, source = self._compute(screen)
        return LlmSettingsView(
            source=source,
            disabled=self._disabled,
            base_url=screen.get(KEY_BASE_URL),
            model=screen.get(KEY_MODEL),
            timeout=float(screen[KEY_TIMEOUT]) if KEY_TIMEOUT in screen else None,
            key_set=self._read_key() is not None,
            description=config.description if config is not None else None,
        )

    # --- mudanças ----------------------------------------------------------------

    def save(self, update: LlmSettingsUpdate) -> LlmSettingsView:
        """Guarda URL, modelo e tempo; troca a chave só se veio uma.

        Mudar de servidor sem escrever a chave de novo é recusado: a chave guardada era para o servidor antigo e
        não deve seguir para outro sem o dono dizer. Grava o banco primeiro e a chave depois: o erro esperado é o do
        banco (ocupado), e assim ele nunca deixa a chave trocada sem a URL.
        """
        validate_update(update)
        values = {
            KEY_BASE_URL: update.base_url.strip(),
            KEY_MODEL: update.model.strip(),
            KEY_TIMEOUT: repr(float(update.timeout)),
        }

        def write(session: Session) -> None:
            for key, value in values.items():
                session.merge(Setting(key=key, value=value))

        with self._lock:
            try:
                saved = self._read_screen().get(KEY_BASE_URL)
                if (
                    update.api_key is None
                    and saved is not None
                    and _origin(saved) != _origin(values[KEY_BASE_URL])
                    and self._read_key() is not None
                ):
                    raise _invalid(
                        "o endereço mudou de servidor: escreva a chave de novo, ou apague a chave guardada antes de salvar"
                    )
                self._db.write(write)
                if update.api_key is not None:
                    self._write_key(update.api_key)
            finally:
                self._invalidate()
        return self.view()

    def clear_key(self) -> LlmSettingsView:
        """Apaga a chave guardada (a URL e o modelo ficam)."""
        with self._lock:
            try:
                self._remove_key()
            finally:
                self._invalidate()
        return self.view()

    def clear(self) -> LlmSettingsView:
        """Apaga tudo o que a tela guardou, chave inclusive: volta ao ambiente, se houver."""

        def remove(session: Session) -> None:
            for key in SCREEN_KEYS:
                row = session.get(Setting, key)
                if row is not None:
                    session.delete(row)

        with self._lock:
            try:
                self._db.write(remove)
                self._remove_key()
            finally:
                self._invalidate()
        return self.view()

    # --- teste -------------------------------------------------------------------

    def test(self) -> LlmTestResult:
        """Uma chamada curta ao LLM em uso. A resposta é sempre uma frase fixa, nunca texto do servidor."""
        config = self.effective()
        if config is None:
            return LlmTestResult(ok=False, message="Não há LLM configurado.")
        try:
            connect_llm(config).complete(TEST_PROMPT, temperature=0.0)
        except LlmError as exc:
            return LlmTestResult(ok=False, message=_explain(str(exc)))
        return LlmTestResult(ok=True, message="O servidor respondeu.")

    # --- por dentro --------------------------------------------------------------

    def _resolve(self) -> tuple[LlmConfig | None, LlmSource]:
        """O que vale agora. O banco é lido **fora** da trava: um banco lento não segura todo mundo na fila."""
        with self._lock:
            if self._cached is not None:
                return self._cached
            generation = self._generation
        value = self._compute()
        with self._lock:
            if generation == self._generation:  # nada mudou enquanto calculava: pode guardar
                self._cached = value
        return value

    def _invalidate(self) -> None:
        """Descarta o cache (e qualquer cálculo em andamento). Quem chama já segura a trava."""
        self._cached = None
        self._generation += 1

    def _compute(self, screen: dict[str, str] | None = None) -> tuple[LlmConfig | None, LlmSource]:
        if self._disabled:
            return None, "none"
        if screen is None:
            screen = self._read_screen()
        if KEY_BASE_URL in screen and KEY_MODEL in screen:
            return (
                LlmConfig(
                    base_url=screen[KEY_BASE_URL],
                    model=screen[KEY_MODEL],
                    api_key=self._read_key(),
                    timeout=float(screen.get(KEY_TIMEOUT, "60")),
                ),
                "screen",
            )
        if self._environment is not None:
            return self._environment, "environment"
        return None, "none"

    def _read_screen(self) -> dict[str, str]:
        def read(session: Session) -> dict[str, str]:
            rows = session.scalars(select(Setting).where(Setting.key.in_(SCREEN_KEYS)))
            return {row.key: row.value for row in rows}

        return self._db.read(read)

    def _read_key(self) -> str | None:
        try:
            tighten(self._key_path, "o arquivo da chave")
            value = self._key_path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return None
        except (OSError, DatabaseError, UnicodeDecodeError):
            print(
                "aviso: não consegui ler o arquivo da chave do LLM; seguindo sem chave.",
                file=sys.stderr,
            )
            return None
        return value or None

    def _remove_key(self) -> None:
        try:
            self._key_path.unlink(missing_ok=True)
        except OSError:
            raise ApiFailure(500, "internal", "não consegui apagar a chave") from None

    def _write_key(self, key: str) -> None:
        """Grava a chave com ``0600`` desde a criação e a põe no lugar de uma vez."""
        temp = self._key_path.with_name(f".{KEY_FILE}.tmp")
        temp.unlink(missing_ok=True)
        try:
            descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(key + "\n")
            os.replace(temp, self._key_path)
        except OSError:
            temp.unlink(missing_ok=True)
            raise ApiFailure(500, "internal", "não consegui gravar a chave") from None


def _explain(detail: str) -> str:
    """Uma frase fixa para o que deu errado: nunca repete o texto do servidor, o endereço nem a chave."""
    status = HTTP_STATUS.search(detail)
    if status is not None:
        code = int(status.group(1))
        if code in (401, 403):
            return f"O servidor recusou a chave (HTTP {code})."
        if code == 404:
            return "O servidor não achou o endereço ou o modelo (HTTP 404)."
        return f"O servidor respondeu com erro (HTTP {code})."
    lowered = detail.lower()
    if "timed out" in lowered or "timeout" in lowered:
        return "O servidor não respondeu a tempo."
    if detail.startswith("falha de conexão"):
        return "Não consegui conectar: confira o endereço e se o servidor está no ar."
    if "formato" in lowered:
        return "O servidor respondeu, mas não no formato chat/completions."
    if "vazia" in lowered:
        return "O modelo devolveu uma resposta vazia."
    return "Não consegui falar com o servidor."
