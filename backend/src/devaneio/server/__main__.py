"""Sobe a mesa em grupo.

Uso: ``devaneio`` (ou ``python -m devaneio.server``) dentro do projeto (ou ``--campanhas DIR --dados DIR [--web DIR]``).

Por padrão escuta só em 127.0.0.1. Com ``--host 0.0.0.0`` o tráfego é HTTP em claro (tokens
inclusive): use rede local, VPN ou um proxy TLS na frente. O editor de campanhas está sempre ligado
(``--sem-editor`` desliga) e só atende pedidos feitos desta máquina, por ``localhost``.
"""

from __future__ import annotations

import argparse
import ipaddress
import math
import os
import sys
import webbrowser
from pathlib import Path

from devaneio.game import LlmConfig, LlmError

from .app import COPILOT_COOLDOWN, SAY_COOLDOWN, TableService
from .catalog import Catalog, CatalogError
from .cli_tools import TOOLS, warn_about_old_saves
from .database import DB_NAME, Database, acquire_instance_lock
from .editor import EditorService
from .errors import DatabaseError
from .files import prepare_data_dir
from .folders import resolve_folders
from .http import make_server
from .migrations import migrate
from .settings_store import SettingsStore
from .static import StaticError, StaticSite
from .storage import Storage


def seconds(raw: str) -> float:
    """Converte um argumento em segundos finitos e não negativos.

    ``nan`` e valores negativos desligariam o limite, e ``inf`` faria o servidor falhar na
    primeira conta.
    """
    value = float(raw)
    if not math.isfinite(value) or value < 0:
        raise argparse.ArgumentTypeError(f"{raw!r} não é um número de segundos finito e >= 0")
    return value


def browser_url(host: str, port: int) -> str:
    """O endereço que o anfitrião abre: ``localhost`` sempre que o servidor escuta nesta máquina."""
    if host in ("::1", "[::1]"):
        return f"http://[::1]:{port}"
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return f"http://{host}:{port}"
    # Escutar em todas as interfaces também vale por localhost.
    if ip.is_loopback or ip.is_unspecified:
        return f"http://localhost:{port}"
    return f"http://[{host}]:{port}" if ip.version == 6 else f"http://{host}:{port}"


def main(argv: list[str] | None = None) -> int:
    """Sobe o servidor da mesa em grupo; devolve o código de saída do processo."""
    arguments = sys.argv[1:] if argv is None else argv
    if arguments[:1] and arguments[0] in TOOLS:
        return TOOLS[arguments[0]](arguments[1:])
    parser = argparse.ArgumentParser(prog="devaneio", description="Devaneio: mesa em grupo.")
    parser.add_argument(
        "--campanhas",
        type=Path,
        default=None,
        help="pasta com campanhas (*.json); padrão: campaigns/ do projeto",
    )
    parser.add_argument(
        "--dados",
        type=Path,
        default=None,
        help="pasta onde as mesas são gravadas; padrão: mesas/ do projeto",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--porta", type=int, default=8765)
    parser.add_argument(
        "--max-mesas", type=int, default=100, help="limite de mesas na pasta de dados"
    )
    parser.add_argument(
        "--intervalo-say",
        type=seconds,
        default=SAY_COOLDOWN,
        help="segundos mínimos entre dois textos livres do mesmo jogador (custo do LLM)",
    )
    parser.add_argument(
        "--intervalo-copiloto",
        type=seconds,
        default=COPILOT_COOLDOWN,
        help="segundos mínimos entre duas consultas ao copiloto do anfitrião (custo do LLM)",
    )
    parser.add_argument(
        "--segredos-no-llm",
        action="store_true",
        help="envia os segredos dos NPCs ao LLM da mesa (a fala dele chega a todos os jogadores)",
    )
    parser.add_argument(
        "--web",
        type=Path,
        default=None,
        help="pasta do build do front (index.html); padrão: o build do projeto, se existir",
    )
    parser.add_argument(
        "--sem-llm", action="store_true", help="ignora o LLM configurado (na tela ou no ambiente)"
    )
    parser.add_argument(
        "--sem-editor",
        action="store_true",
        help="desliga o editor de campanhas (ligado por padrão; só atende pedidos desta máquina)",
    )
    parser.add_argument(
        "--sem-navegador", action="store_true", help="não abre o navegador ao subir"
    )
    args = parser.parse_args(arguments)

    try:
        campaigns_dir, data_dir, web_dir = resolve_folders(args, Path.cwd())
        catalog = Catalog(campaigns_dir)
        environment = None if args.sem_llm else LlmConfig.from_env(os.environ)
        static = StaticSite(web_dir) if web_dir is not None else None
        data_dir = prepare_data_dir(data_dir)
        instance_lock = acquire_instance_lock(data_dir)  # fica aberto até o processo sair
        db = Database(data_dir / DB_NAME)
        migrate(db)
        settings = SettingsStore(db, data_dir, environment=environment, disabled=args.sem_llm)
        storage = Storage(db, max_tables=args.max_mesas)
    except (
        ValueError,
        CatalogError,
        DatabaseError,
        LlmError,
        StaticError,
        OSError,
    ) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1
    service = TableService(
        catalog,
        storage,
        llm=settings.effective,
        say_cooldown=args.intervalo_say,
        copilot_cooldown=args.intervalo_copiloto,
        llm_secrets=args.segredos_no_llm,
    )
    editor = None if args.sem_editor else EditorService(catalog, storage, settings)
    server = make_server(args.host, args.porta, service, static, editor)
    port = server.server_address[1]
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        print(
            f"aviso: escutando em {args.host}: HTTP em claro, inclusive tokens. "
            "Use rede local, VPN ou um proxy TLS.",
            file=sys.stderr,
        )
    url = browser_url(args.host, port)
    print(f"Devaneio: mesa em http://{args.host}:{port} ({len(catalog.summaries())} campanha(s))")
    print(f"Campanhas em {campaigns_dir.resolve()}; mesas em {data_dir.resolve()}.")
    warn_about_old_saves(storage, catalog, data_dir)
    if static is None:
        print(
            "O app ainda não foi construído (cd frontend/app && npm run build): só a API responde.",
            file=sys.stderr,
        )
    # Escutando só num endereço da rede, `localhost` nem conecta: o editor não está ao alcance e não se promete.
    if (
        editor is not None
        and static is not None
        and url.startswith(("http://localhost:", "http://[::1]:"))
    ):
        print(f"Para criar e editar campanhas, abra {url} neste computador.")
    llm = settings.effective()
    if llm is not None:
        print(f"LLM ligado ({llm.description}): o contexto das mesas vai a esse servidor.")
    if static is not None and not args.sem_navegador:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nencerrando.")
    finally:
        server.server_close()
        db.close()
        if instance_lock is not None:
            instance_lock.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
