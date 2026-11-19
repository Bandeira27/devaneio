"""Do arquivo para o banco: importa as partidas em JSON de mesa (as que o servidor guardava antes do banco).

O arquivo continua o formato do CLI (``SaveFile``); aqui ele cruza a fronteira para o banco. A importação é
idempotente (uma mesa que já existe é pulada), preserva o id, os tokens e o convite (só hash existe) e **nunca
toca nos arquivos originais**. O que não serve é recusado com o motivo, sem copiar nada do conteúdo do arquivo.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from devaneio.game import GameError, SaveFile, open_save

from .catalog import Catalog
from .records import record_from_save
from .storage import TABLE_ID, Storage

MAX_SAVE_BYTES = (
    16 * 1024 * 1024
)  # uma partida de verdade tem poucos MB; acima disso o arquivo não é uma


@dataclass
class ImportReport:
    """O que a importação fez: o que entrou, o que já estava lá e o que foi recusado (com o motivo)."""

    imported: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    refused: list[tuple[str, str]] = field(default_factory=list)


def find_saves(source: Path) -> list[Path]:
    """Os arquivos de partida de uma fonte: o próprio arquivo, ou os ``<id>.json`` de uma pasta (sem descer nas subpastas)."""
    source = Path(source)
    if source.is_dir():
        return sorted(p for p in source.glob("*.json") if p.is_file() and TABLE_ID.match(p.stem))
    return [source]


def import_saves(
    storage: Storage, catalog: Catalog, sources: Iterable[Path], *, apply: bool = True
) -> ImportReport:
    """Importa as partidas de mesa das fontes (arquivos ou pastas) para o banco.

    Com ``apply=False`` nada é gravado: ``imported`` diz o que **entraria** e ``refused``, o que seria recusado e por quê
    (serve para avisar quem sobe o servidor, sem mexer em nada).
    """
    report = ImportReport()
    for source in sources:
        for path in find_saves(source):
            _import_one(storage, catalog, path, report, apply=apply)
    return report


def _import_one(
    storage: Storage, catalog: Catalog, path: Path, report: ImportReport, *, apply: bool
) -> None:
    name = path.name
    if not TABLE_ID.match(path.stem):
        report.refused.append((name, "o nome do arquivo não é um id de mesa (16 letras e números)"))
        return
    if storage.exists(path.stem):
        report.skipped.append(path.stem)
        return
    try:
        if path.stat().st_size > MAX_SAVE_BYTES:
            report.refused.append((name, "o arquivo é grande demais para uma partida"))
            return
        data = SaveFile.model_validate_json(path.read_text(encoding="utf-8"))
    except OSError:
        report.refused.append((name, "não consegui ler o arquivo"))
        return
    except (ValidationError, ValueError):
        report.refused.append((name, "não é uma partida do Devaneio"))
        return
    if data.table is None:
        report.refused.append((name, "é uma partida solo (sem mesa em grupo)"))
        return
    campaign_path = (path.parent / data.campaign_path).resolve()
    try:
        reference = catalog.relative(campaign_path)
    except ValueError:
        report.refused.append((name, "a campanha dela está fora da pasta de campanhas"))
        return
    try:
        open_save(data, campaign_path, label=path.stem)
    except GameError:
        report.refused.append((name, "a partida não combina com a campanha ou com as regras"))
        return
    except (OSError, ValueError):
        report.refused.append((name, "não consegui abrir a campanha dela"))
        return
    record = record_from_save(data, reference)
    try:
        modified = path.stat().st_mtime
    except OSError:
        report.refused.append((name, "não consegui ler o arquivo"))
        return
    if not apply or storage.create(path.stem, record, updated_at=modified):
        report.imported.append(path.stem)
    else:
        report.refused.append((name, "o servidor já tem o máximo de mesas (--max-mesas)"))
