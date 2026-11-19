"""Onde ficam as pastas do projeto: campanhas, dados (o banco) e o build do app.

Compartilhado pelo servidor (``__main__``) e pelas ferramentas de linha de comando (``cli_tools``).
"""

from __future__ import annotations

import argparse
from pathlib import Path

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
