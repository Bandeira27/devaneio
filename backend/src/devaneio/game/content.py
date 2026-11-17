"""Conteúdo da campanha: o sistema de regras e o pacote de narração, do autor ou embutidos.

O id vem da campanha (``rules_id``, ``narration_id``). É procurado primeiro em ``sistemas/`` ou
``narracoes/`` ao lado do arquivo da campanha e, se não houver, entre os embutidos. O arquivo do
autor é dado não confiável (rule 05): o id é um slug (sem ``..``), o arquivo resolvido precisa ficar
dentro da pasta da campanha, o tamanho é limitado antes de ler, e todo erro vira ``GameError`` em
português sem o caminho absoluto.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from pydantic import ValidationError

from devaneio.narration import (
    NarrationPack,
    builtin_pack_dict,
    load_pack_extending,
)
from devaneio.rules import (
    RuleSystem,
    builtin_rules_dict,
    load_rules_extending,
    validate_campaign_against_rules,
)
from devaneio.schema import ID_REGEX, Campaign, load_campaign

from .errors import GameError

_T = TypeVar("_T")

MAX_CONTENT_BYTES = 256 * 1024
RULES_DIR = "sistemas"
NARRATION_DIR = "narracoes"


def load_campaign_content(campaign_path: Path) -> tuple[Campaign, RuleSystem, NarrationPack]:
    """A campanha, o sistema e o pacote que ela pede, já conferidos entre si."""
    campaign_path = Path(campaign_path)
    campaign = load_campaign(campaign_path.read_text(encoding="utf-8"))
    rules = load_rules_for(campaign, campaign_path.parent)
    errors = validate_campaign_against_rules(campaign, rules)
    if errors:
        raise GameError(joined(f"campanha '{campaign.id}' incompatível com '{rules.id}'", errors))
    return campaign, rules, load_pack_for(campaign, campaign_path.parent)


def load_rules_for(campaign: Campaign, campaign_dir: Path) -> RuleSystem:
    """O sistema de regras que a campanha cita, procurado ao lado dela e depois nos embutidos."""
    return load_rules_by_id(campaign.rules_id, campaign_dir)


def load_rules_by_id(rules_id: str, campaign_dir: Path) -> RuleSystem:
    """Um sistema de regras pelo id, procurado em ``sistemas/`` ao lado das campanhas e depois nos embutidos."""
    return _load(
        "sistema de regras",
        rules_id,
        campaign_dir / RULES_DIR,
        builtin_rules_dict,
        load_rules_extending,
    )


def rules_ids(campaign_dir: Path) -> list[str]:
    """Os ids de sistema que uma campanha desta pasta pode citar: os do autor e o embutido."""
    own = sorted(
        path.stem
        for path in (campaign_dir / RULES_DIR).glob("*.json")
        if ID_REGEX.fullmatch(path.stem)
    )
    return [*dict.fromkeys(["default", *own])]


def load_pack_for(campaign: Campaign, campaign_dir: Path) -> NarrationPack:
    """O pacote de narração que a campanha cita, procurado ao lado dela e depois nos embutidos."""
    return _load(
        "pacote de narração",
        campaign.narration_id,
        campaign_dir / NARRATION_DIR,
        builtin_pack_dict,
        load_pack_extending,
    )


def joined(head: str, errors: list[str]) -> str:
    """Um título seguido da lista de erros, um por linha."""
    return head + ":\n" + "\n".join(f"- {e}" for e in errors)


def _load(
    label: str,
    content_id: str,
    folder: Path,
    builtin: Callable[[str], dict[str, Any]],
    loader: Callable[[Any, Callable[[str], dict[str, Any]]], _T],
) -> _T:
    """Arquivo do autor (se houver) ou embutido; o pai de um ``extends`` segue a mesma regra."""

    def parent(parent_id: str) -> dict[str, Any]:
        path = _author_file(label, parent_id, folder)
        if path is not None:
            return _read_json(label, path)
        try:
            return builtin(parent_id)
        except ValueError:
            raise _not_found(label, parent_id, folder) from None

    path = _author_file(label, content_id, folder)
    if path is None:
        try:
            data = builtin(content_id)
        except ValueError:
            raise _not_found(label, content_id, folder) from None
    else:
        data = _read_json(label, path)
    try:
        return loader(data, parent)
    except GameError:
        raise
    except ValueError as exc:
        origin = f"{folder.name}/{path.name}" if path is not None else "embutido"
        raise GameError(f"{label} '{content_id}' ({origin}): {_explain(exc)}") from None


def _author_file(label: str, content_id: str, folder: Path) -> Path | None:
    try:
        path = folder / f"{content_id}.json"
        if not path.is_file():
            return None
        resolved = path.resolve()
        if not resolved.is_relative_to(folder.resolve()):
            raise GameError(f"{label} '{content_id}': o arquivo aponta para fora de {folder.name}/")
    except OSError as exc:
        raise GameError(f"{label} '{content_id}': não foi possível ler o arquivo") from exc
    return resolved


def _read_json(label: str, path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            raw = handle.read(
                MAX_CONTENT_BYTES + 1
            )  # o teto vale para o que foi lido, não para o stat
        if len(raw) > MAX_CONTENT_BYTES:
            raise GameError(
                f"{label} '{path.stem}': arquivo maior que {MAX_CONTENT_BYTES // 1024} KiB"
            )
        data = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise GameError(f"{label} '{path.stem}': não foi possível ler o arquivo") from exc
    except json.JSONDecodeError as exc:
        raise GameError(
            f"{label} '{path.stem}': JSON inválido na linha {exc.lineno}: {exc.msg}"
        ) from None
    except RecursionError:
        raise GameError(f"{label} '{path.stem}': JSON aninhado demais") from None
    if not isinstance(data, dict):
        raise GameError(f"{label} '{path.stem}': o arquivo precisa ser um objeto JSON")
    return data


def _explain(exc: ValueError) -> str:
    """Erro do Pydantic só com onde e o quê, sem o valor do arquivo (nem a URL de ajuda)."""
    if isinstance(exc, ValidationError):
        return "; ".join(
            f"{'.'.join(str(part) for part in e['loc']) or 'arquivo'}: {e['msg']}"
            for e in exc.errors(include_url=False, include_input=False)
        )
    return str(exc)


def _not_found(label: str, content_id: str, folder: Path) -> GameError:
    return GameError(
        f"{label} '{content_id}' não encontrado (procurado em {folder.name}/ ao lado da "
        "campanha e entre os embutidos)"
    )
