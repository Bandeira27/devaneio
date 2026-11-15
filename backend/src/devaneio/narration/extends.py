"""``extends`` de pacotes de narração: o filho substitui as chaves iguais e herda o resto.

Mesma ideia dos sistemas de regras, um nível só. O resultado passa pela validação de sempre
(``load_pack``): toda referência ``#x#`` precisa existir, também nas regras herdadas.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from typing import Annotated, Any, Literal

from pydantic import Field

from devaneio.schema.common import Id, StrictModel

from .pack import NarrationPack, builtin_pack_json, load_pack


class PackExtendsError(ValueError):
    """``extends`` mal usado (pai inexistente, cadeia, id repetido)."""


class NarrationPackExtension(StrictModel):
    """Pacote que estende outro. Só ``id`` e ``extends`` são obrigatórios; ``language`` é herdada
    se omitida e cada chave de ``rules`` substitui a de mesmo nome do pai."""

    schema_version: Literal[1] = 1
    id: Id
    extends: Id
    language: str | None = None
    rules: dict[str, Annotated[list[str], Field(min_length=1)]] = Field(default_factory=dict)


def merge_pack(parent: dict[str, Any], extension: dict[str, Any]) -> dict[str, Any]:
    """Pai mais as chaves declaradas no filho (``extends`` não entra no resultado). Não muta."""
    merged = copy.deepcopy(parent)
    for key, value in extension.items():
        if key == "extends":
            continue
        if key == "rules":
            merged["rules"] = {**merged.get("rules", {}), **value}
        else:
            merged[key] = value
    return merged


def builtin_pack_dict(pack_id: str) -> dict[str, Any]:
    """O pacote embutido como dict (para ser pai de um ``extends``)."""
    parsed: dict[str, Any] = json.loads(builtin_pack_json(pack_id))
    return parsed


def load_pack_extending(data: Any, load_parent: Callable[[str], dict[str, Any]]) -> NarrationPack:
    """Carrega um pacote, resolvendo ``extends`` por ``load_parent`` (id -> dict do pai, que
    levanta ``ValueError`` se não existe). Sem ``extends``, é um ``load_pack`` comum."""
    raw = json.loads(data) if isinstance(data, (str, bytes, bytearray)) else data
    if not isinstance(raw, dict) or "extends" not in raw:
        return load_pack(raw)
    extension = NarrationPackExtension.model_validate(raw)
    if extension.id == extension.extends:
        raise PackExtendsError(f"pacote '{extension.id}' não pode estender a si mesmo")
    parent = load_parent(extension.extends)
    if "extends" in parent:
        raise PackExtendsError(
            f"'{extension.extends}' já estende outro pacote; só um nível de extends é permitido"
        )
    if parent.get("id") == extension.id:
        raise PackExtendsError(f"'{extension.id}' repete o id do pacote pai")
    return load_pack(merge_pack(parent, extension.model_dump(mode="json", exclude_unset=True)))
