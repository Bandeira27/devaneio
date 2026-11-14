"""Pacote de narração: a 'voz' do narrador como dados, validada na carga."""

from __future__ import annotations

from collections.abc import Iterable
from importlib import resources
from typing import Annotated, Any, Literal

from pydantic import Field

from devaneio.schema.common import Id, StrictModel

from .grammar import Grammar

# Variáveis que cada tipo de evento oferece aos templates. Regras cujo nome começa com o
# tipo ("check.success", "move") só podem usar estas; auxiliares herdam das raízes.
EVENT_VARIABLES: dict[str, tuple[str, ...]] = {
    "check": ("ator", "habilidade", "dificuldade", "total", "margem", "desfecho"),
    "damage": ("atacante", "alvo", "arma", "fonte", "dano", "hp", "hp_max"),
    "move": ("origem", "destino", "descricao"),
    "heal": ("alvo", "fonte", "cura", "hp", "hp_max"),
    "rest": ("curados",),
    "character_joined": ("ator", "hp"),
    "turn_end": ("turno",),
    "director": ("tensao", "local"),
    "beat_activated": ("marco", "descricao"),
    "beat_done": ("marco", "descricao"),
    "beat_failed": ("marco", "descricao"),
}


class NarrationIntegrityError(ValueError):
    def __init__(self, errors: Iterable[str]) -> None:
        self.errors = list(errors)
        super().__init__(
            "Pacote de narração inconsistente:\n" + "\n".join(f"- {e}" for e in self.errors)
        )


class NarrationPack(StrictModel):
    schema_version: Literal[1] = 1
    id: Id
    language: str
    rules: dict[str, Annotated[list[str], Field(min_length=1)]] = Field(min_length=1)


def validate_pack(pack: NarrationPack) -> list[str]:
    """Toda referência ``#x#`` é regra ou variável do tipo de evento da raiz."""
    grammar = Grammar(pack.rules)
    roots = {
        key: EVENT_VARIABLES[key.split(".")[0]]
        for key in pack.rules
        if key.split(".")[0] in EVENT_VARIABLES
    }
    return [f"referência indefinida em {problem}" for problem in grammar.undefined(roots)]


def load_pack(data: Any) -> NarrationPack:
    if isinstance(data, (str, bytes, bytearray)):
        pack = NarrationPack.model_validate_json(data)
    else:
        pack = NarrationPack.model_validate(data)
    errors = validate_pack(pack)
    if errors:
        raise NarrationIntegrityError(errors)
    return pack


def builtin_pack_json(pack_id: str) -> str:
    resource = resources.files("devaneio.narration").joinpath(f"data/{pack_id}.json")
    if not resource.is_file():
        raise ValueError(f"pacote de narração '{pack_id}' não encontrado")
    return resource.read_text(encoding="utf-8")


def load_builtin_pack(pack_id: str = "pt-br") -> NarrationPack:
    return load_pack(builtin_pack_json(pack_id))
