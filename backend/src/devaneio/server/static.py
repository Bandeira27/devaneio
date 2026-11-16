"""Arquivos estáticos do front (o build do app), confinados a uma pasta.

Só existe com ``--web DIR``. O caminho vem da rede e não é confiável (rule 05, item 23): é
decodificado uma vez e recusado se tiver ``..``, NUL, barra invertida, segmento oculto ou se for
diretório; o arquivo resolvido precisa ficar dentro da pasta (symlink para fora é recusado); o tipo sai
de uma lista fechada de extensões (sem ``.map``), então nada além do build é entregue.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

MAX_STATIC_BYTES = 8 * 1024 * 1024  # o build do app tem poucas centenas de KiB por arquivo

MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".webmanifest": "application/manifest+json",
    ".txt": "text/plain; charset=utf-8",
}

# ``style-src 'unsafe-inline'`` é risco aceito: o Angular injeta estilos de componente em execução.
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; "
    "base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
)
SECURITY_HEADERS = {
    "Content-Security-Policy": CSP,
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
}
IMMUTABLE = "public, max-age=31536000, immutable"
REVALIDATE = "no-cache"
# O hash do Angular no nome (``main-3F8K2LQA.js``): só maiúsculas e dígitos, para ``logo-devaneio.svg``
# não ficar um ano em cache ``immutable``.
_HASHED = re.compile(r"[-.][A-Z0-9]{8,}\.[A-Za-z0-9]+$")


class StaticError(ValueError):
    """Pasta do front inválida (não existe ou não tem ``index.html``)."""


@dataclass(frozen=True)
class StaticFile:
    """Um arquivo a servir: o caminho, o tipo e o cache."""

    path: Path
    content_type: str
    cache_control: str
    size: int


class StaticSite:
    """A pasta do app (build do front) servida pela mesma origem da API."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise StaticError(f"a pasta do front '{root}' não existe")
        if not (self.root / "index.html").is_file():
            raise StaticError(f"a pasta do front '{root}' não tem index.html (rode o build do app)")

    def lookup(self, raw_path: str) -> StaticFile | None:
        """O arquivo de um caminho de URL, ou nada para qualquer recusa.

        O arquivo de um caminho de URL (ainda codificado), ou ``None`` para qualquer recusa:
        o chamador responde 404 igual para o que não existe e para o que é proibido.
        """
        try:
            decoded = unquote(raw_path, errors="strict")
        except UnicodeDecodeError:
            return None
        if "\x00" in decoded or "\\" in decoded or not decoded.startswith("/"):
            return None
        parts = decoded.split("/")[1:]
        if parts == [""]:
            parts = ["index.html"]
        if any(p in ("", ".", "..") or p.startswith(".") for p in parts):
            return None
        candidate = self.root.joinpath(*parts)
        if MIME.get(candidate.suffix.lower()) is None:
            return None
        try:
            resolved = candidate.resolve()
            if not resolved.is_relative_to(self.root) or not resolved.is_file():
                return None
            size = resolved.stat().st_size
        except OSError:
            return None
        # O alvo de um symlink também passa pela lista de tipos e pelos segmentos ocultos.
        content_type = MIME.get(resolved.suffix.lower())
        target_parts = resolved.relative_to(self.root).parts
        if content_type is None or any(p.startswith(".") for p in target_parts):
            return None
        if size > MAX_STATIC_BYTES:
            return None
        cache = IMMUTABLE if _HASHED.search(resolved.name) else REVALIDATE
        return StaticFile(resolved, content_type, cache, size)
