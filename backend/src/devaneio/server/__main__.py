"""``python -m devaneio.server --campanhas DIR --dados DIR [--host H] [--porta P]``

Sobe a mesa em grupo. Por padrão escuta só em 127.0.0.1: com ``--host 0.0.0.0`` o tráfego
é HTTP em claro (tokens inclusive); use rede local, VPN ou um proxy TLS na frente.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from devaneio.llm import LlmConfig, LlmError

from .app import TableService
from .catalog import Catalog, CatalogError
from .http import make_server
from .storage import Storage


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="devaneio.server", description="Devaneio: mesa em grupo.")
    parser.add_argument(
        "--campanhas", type=Path, required=True, help="pasta com campanhas (*.json)"
    )
    parser.add_argument(
        "--dados", type=Path, required=True, help="pasta onde as mesas são gravadas"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--porta", type=int, default=8765)
    parser.add_argument(
        "--max-mesas", type=int, default=100, help="limite de mesas na pasta de dados"
    )
    parser.add_argument(
        "--sem-llm", action="store_true", help="ignora o LLM configurado no ambiente"
    )
    args = parser.parse_args(argv)

    try:
        catalog = Catalog(args.campanhas)
        llm = None if args.sem_llm else LlmConfig.from_env(os.environ)
    except (CatalogError, LlmError, OSError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1
    service = TableService(catalog, Storage(args.dados, max_tables=args.max_mesas), llm=llm)
    server = make_server(args.host, args.porta, service)
    port = server.server_address[1]
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        print(
            f"aviso: escutando em {args.host}: HTTP em claro, inclusive tokens. "
            "Use rede local, VPN ou um proxy TLS.",
            file=sys.stderr,
        )
    print(f"Devaneio: mesa em http://{args.host}:{port} ({len(catalog.summaries())} campanha(s))")
    if llm is not None:
        print(f"LLM ligado ({llm.description}): o contexto das mesas vai a esse servidor.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nencerrando.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
