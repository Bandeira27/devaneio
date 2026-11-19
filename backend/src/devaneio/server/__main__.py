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
from .database import DB_NAME, Database, acquire_instance_lock
from .editor import EditorService
from .errors import DatabaseError
from .files import prepare_data_dir
from .http import make_server
from .migrations import migrate
from .settings_store import SettingsStore
from .static import StaticError, StaticSite
from .storage import Storage
from .transfer import import_saves


def seconds(raw: str) -> float:
    """Converte um argumento em segundos finitos e não negativos.

    ``nan`` e valores negativos desligariam o limite, e ``inf`` faria o servidor falhar na
    primeira conta.
    """
    value = float(raw)
    if not math.isfinite(value) or value < 0:
        raise argparse.ArgumentTypeError(f"{raw!r} não é um número de segundos finito e >= 0")
    return value


BUILD = Path("frontend/app/dist/devaneio/browser")


def project_root(start: Path) -> Path | None:
    """A pasta do projeto: a atual ou a de cima, a que tem ``campaigns/`` e ``backend/`` (o marcador do Devaneio).

    Só ``campaigns/`` bastaria para achar as campanhas, mas o editor grava nela: uma pasta qualquer com esse nome,
    sem ser do Devaneio, não vira o destino sem o anfitrião pedir.
    """
    for folder in (start, start.parent):
        if (folder / "campaigns").is_dir() and (folder / "backend").is_dir():
            return folder
    return None


def resolve_folders(args: argparse.Namespace, cwd: Path) -> tuple[Path, Path, Path | None]:
    """Campanhas, mesas e app: o que veio na linha de comando, senão o padrão da pasta do projeto.

    Levanta ``ValueError`` (em pt-br) se faltar uma pasta e o projeto não for achado. O app só entra
    se já foi construído; sem ele o servidor responde só a API.
    """
    root = project_root(cwd)
    campaigns = args.campanhas or (root / "campaigns" if root else None)
    data = args.dados or (root / "mesas" if root else None)
    if campaigns is None or data is None:
        raise ValueError(
            "não achei a pasta do projeto (a que tem 'campaigns/' e 'backend/'): rode de dentro dela "
            "ou passe --campanhas e --dados"
        )
    web = args.web
    if web is None and root is not None and (root / BUILD / "index.html").is_file():
        web = root / BUILD
    return Path(campaigns), Path(data), web


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


MAX_LISTED = 10  # quantos arquivos recusados o aviso da subida lista; o resto vira "e mais N"


def warn_about_old_saves(storage: Storage, catalog: Catalog, data_dir: Path) -> None:
    """Avisa, ao subir, das partidas em JSON da pasta de dados que ainda não estão no banco, e das que não podem entrar.

    Só olha (``apply=False``): nada é gravado nem movido. Os recusados saem com o motivo, para o aviso não ficar
    pedindo um ``importar`` que não resolve e o dono saber o que fazer com cada arquivo.
    """
    found = import_saves(storage, catalog, [data_dir], apply=False)
    if found.imported:
        print(
            f"aviso: {len(found.imported)} partida(s) em JSON na pasta de dados ainda não estão no banco: "
            "rode 'devaneio importar' (com o servidor parado) para trazê-las.",
            file=sys.stderr,
        )
    if found.refused:
        print(
            f"aviso: {len(found.refused)} arquivo(s) .json na pasta de dados não podem ser importados "
            "(o 'devaneio importar' também os recusa; mova-os para outra pasta para este aviso parar):",
            file=sys.stderr,
        )
        for name, reason in found.refused[:MAX_LISTED]:
            print(f"  {name}: {reason}", file=sys.stderr)
        if len(found.refused) > MAX_LISTED:
            print(f"  ... e mais {len(found.refused) - MAX_LISTED}.", file=sys.stderr)


def import_main(argv: list[str]) -> int:
    """``devaneio importar``: traz para o banco as partidas de mesa em JSON; devolve o código de saída."""
    parser = argparse.ArgumentParser(
        prog="devaneio importar",
        description="Importa partidas de mesa em JSON (as de antes do banco) para o banco do servidor. "
        "Não altera os arquivos originais e pula o que já foi importado.",
    )
    parser.add_argument(
        "fontes",
        nargs="*",
        type=Path,
        help="arquivos ou pastas com <id>.json; padrão: a pasta de dados",
    )
    parser.add_argument("--campanhas", type=Path, default=None, help="pasta das campanhas")
    parser.add_argument(
        "--dados", type=Path, default=None, help="pasta de dados (onde fica o banco)"
    )
    parser.add_argument(
        "--max-mesas",
        type=int,
        default=None,
        help="limite de mesas no banco; padrão: sem limite (importar é decisão do dono da máquina)",
    )
    args = parser.parse_args(argv)
    args.web = None
    try:
        campaigns_dir, data_dir, _ = resolve_folders(args, Path.cwd())
        catalog = Catalog(campaigns_dir)
        data_dir = prepare_data_dir(data_dir)
        instance_lock = acquire_instance_lock(data_dir)  # recusa se o servidor está de pé
        db = Database(data_dir / DB_NAME)
        try:
            migrate(db)
            storage = Storage(
                db, max_tables=sys.maxsize if args.max_mesas is None else args.max_mesas
            )
            report = import_saves(storage, catalog, args.fontes or [data_dir])
        finally:
            db.close()
            if instance_lock is not None:
                instance_lock.close()
    except (ValueError, CatalogError, DatabaseError, OSError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1
    print(f"Importadas: {len(report.imported)}. Já estavam no banco: {len(report.skipped)}.")
    for name, reason in report.refused:
        print(f"recusada: {name}: {reason}", file=sys.stderr)
    return 1 if report.refused else 0


def main(argv: list[str] | None = None) -> int:
    """Sobe o servidor da mesa em grupo; devolve o código de saída do processo."""
    arguments = sys.argv[1:] if argv is None else argv
    if arguments[:1] == ["importar"]:
        return import_main(arguments[1:])
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
