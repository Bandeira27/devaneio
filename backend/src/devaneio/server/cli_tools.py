"""As ferramentas de linha de comando do servidor, que trabalham no banco com o servidor parado.

``devaneio importar`` (partidas JSON de antes do banco para dentro), ``devaneio exportar`` (uma mesa para fora, no
formato do CLI) e ``devaneio backup`` (uma cópia consistente do banco). As três pegam o mesmo ``flock`` do servidor:
um banco, um processo. Nenhuma toca na chave do LLM.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from devaneio.game import GameError, build_save

from .catalog import Catalog, CatalogError
from .database import DB_NAME, Database, acquire_instance_lock
from .errors import ApiFailure, DatabaseError
from .files import prepare_data_dir
from .folders import resolve_folders
from .migrations import migrate
from .records import TableRecords
from .storage import TABLE_ID, Storage
from .transfer import import_saves

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


def _parser(name: str, description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=f"devaneio {name}", description=description)
    parser.add_argument("--campanhas", type=Path, default=None, help="pasta das campanhas")
    parser.add_argument(
        "--dados", type=Path, default=None, help="pasta de dados (onde fica o banco)"
    )
    parser.set_defaults(
        web=None
    )  # resolve_folders também acha o build do app; as ferramentas não o usam
    return parser


@contextmanager
def _opened(
    data_dir: Path, *, max_tables: int = sys.maxsize, migrate_db: bool = True
) -> Iterator[tuple[Database, Storage]]:
    """O banco aberto com a trava do servidor (recusa se ele está de pé); fecha tudo ao sair."""
    data_dir = prepare_data_dir(data_dir)
    lock = acquire_instance_lock(data_dir)
    db = Database(data_dir / DB_NAME)
    try:
        if migrate_db:
            migrate(db)
        yield db, Storage(db, max_tables=max_tables)
    finally:
        db.close()
        if lock is not None:
            lock.close()


def import_main(argv: list[str]) -> int:
    """``devaneio importar``: traz para o banco as partidas de mesa em JSON; devolve o código de saída."""
    parser = _parser(
        "importar",
        "Importa partidas de mesa em JSON (as de antes do banco) para o banco do servidor. "
        "Não altera os arquivos originais e pula o que já foi importado.",
    )
    parser.add_argument(
        "fontes",
        nargs="*",
        type=Path,
        help="arquivos ou pastas com <id>.json; padrão: a pasta de dados",
    )
    parser.add_argument(
        "--max-mesas",
        type=int,
        default=None,
        help="limite de mesas no banco; padrão: sem limite (importar é decisão do dono da máquina)",
    )
    args = parser.parse_args(argv)
    try:
        campaigns_dir, data_dir, _ = resolve_folders(args, Path.cwd())
        catalog = Catalog(campaigns_dir)
        limit = sys.maxsize if args.max_mesas is None else args.max_mesas
        with _opened(data_dir, max_tables=limit) as (_, storage):
            report = import_saves(storage, catalog, args.fontes or [data_dir])
    except (ValueError, CatalogError, DatabaseError, OSError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1
    print(f"Importadas: {len(report.imported)}. Já estavam no banco: {len(report.skipped)}.")
    for name, reason in report.refused:
        print(f"recusada: {name}: {reason}", file=sys.stderr)
    return 1 if report.refused else 0


def export_main(argv: list[str]) -> int:
    """``devaneio exportar``: grava uma mesa (ativa ou arquivada) como arquivo de partida do CLI; devolve o código de saída."""
    parser = _parser(
        "exportar",
        "Exporta uma mesa para um arquivo de partida (o formato do jogo solo no terminal). Por padrão sem os hashes de "
        "token e de convite; com --com-mesa leva a mesa inteira, e o arquivo volta ao banco por 'devaneio importar' "
        "(mantenha o nome <id>.json: é por ele que a mesa é reconhecida).",
    )
    parser.add_argument("mesa", help="o id da mesa (16 letras e números)")
    parser.add_argument(
        "--saida", type=Path, default=None, help="o arquivo a gravar; padrão: <id>.json aqui"
    )
    parser.add_argument(
        "--com-mesa",
        action="store_true",
        help="inclui jogadores, hashes de token e de convite e a fase (para reimportar)",
    )
    args = parser.parse_args(argv)
    if (
        TABLE_ID.match(args.mesa) is None
    ):  # antes de montar qualquer caminho com o que veio da linha de comando
        print("erro: o id da mesa tem 16 letras (a a f) e números", file=sys.stderr)
        return 1
    try:
        campaigns_dir, data_dir, _ = resolve_folders(args, Path.cwd())
        if not (data_dir / DB_NAME).is_file():
            print(f"erro: não há banco em {data_dir}", file=sys.stderr)
            return 1
        catalog = Catalog(campaigns_dir)
        target = (args.saida or Path(f"{args.mesa}.json")).resolve()
        with _opened(data_dir) as (_, storage):
            session = TableRecords(storage, catalog).load(args.mesa, scope="any")
        data = build_save(session, os.path.relpath(session.campaign_path, target.parent))
        if not args.com_mesa:
            data = data.model_copy(update={"table": None})
        _write_new(target, data.model_dump_json(indent=2) + "\n")
    except FileExistsError:
        print(
            f"erro: {args.saida or args.mesa + '.json'} já existe; escolha outro --saida",
            file=sys.stderr,
        )
        return 1
    except ApiFailure as exc:
        print(f"erro: {exc.message}", file=sys.stderr)
        return 1
    except RuntimeError:
        print(f"erro: não consegui ler a mesa {args.mesa}", file=sys.stderr)
        return 1
    except (ValueError, GameError, CatalogError, DatabaseError, OSError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1
    print(f"Mesa {args.mesa} exportada para {target}.")
    return 0


def backup_main(argv: list[str]) -> int:
    """``devaneio backup``: copia o banco inteiro (mesas ativas e arquivadas) para um arquivo; devolve o código de saída."""
    parser = _parser(
        "backup",
        "Copia o banco do servidor para um arquivo, de forma consistente. A cópia só do seu usuário (0600), com os "
        "hashes de token e de convite e SEM a chave do LLM (que fica à parte, em llm.key).",
    )
    parser.add_argument("destino", type=Path, help="o arquivo da cópia (não pode existir)")
    args = parser.parse_args(argv)
    try:
        _, data_dir, _ = resolve_folders(args, Path.cwd())
        if not (data_dir / DB_NAME).is_file():
            print(f"erro: não há banco em {data_dir}", file=sys.stderr)
            return 1
        destination = args.destino.resolve()
        if destination.parent == data_dir.resolve() and destination.name.startswith(DB_NAME):
            print("erro: o destino não pode ser um arquivo do próprio banco", file=sys.stderr)
            return 1
        with _opened(data_dir, migrate_db=False) as (db, _):
            db.backup_to(destination, exclusive=True)
    except FileExistsError:
        print(f"erro: {args.destino} já existe; escolha outro destino", file=sys.stderr)
        return 1
    except (ValueError, DatabaseError, OSError, sqlite3.Error) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1
    print(f"Cópia do banco gravada em {destination} (sem a chave do LLM).")
    return 0


def _write_new(path: Path, text: str) -> None:
    """Grava um arquivo novo só do dono; ``FileExistsError`` se já existe (nunca sobrescreve)."""
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(text)


TOOLS: dict[str, Callable[[list[str]], int]] = {
    "importar": import_main,
    "exportar": export_main,
    "backup": backup_main,
}
