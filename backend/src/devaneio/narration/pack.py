"""Pacote de narração: a 'voz' do narrador como dados, validada na carga."""

from __future__ import annotations

from collections.abc import Iterable
from importlib import resources
from typing import Annotated, Any, Literal

from pydantic import Field

from devaneio.schema.common import Id, StrictModel

from .grammar import MAX_EXPANDED_CHARS, Grammar

# Variáveis que cada tipo de evento oferece aos templates das regras que começam por ele.
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
    "reveal": ("fato",),
}


# Variantes que o narrador escolhe por tipo de evento (regras "tipo.variante").
EVENT_VARIANTS: dict[str, tuple[str, ...]] = {
    "check": ("critical_failure", "failure", "success", "critical_success"),
    "damage": ("golpe", "golpe_queda", "fonte", "fonte_queda"),
    "director": ("calmo", "tenso", "critico"),
}


class NarrationIntegrityError(ValueError):
    """Pacote de narração com referências que não existem; `errors` lista todas."""

    def __init__(self, errors: Iterable[str]) -> None:
        self.errors = list(errors)
        super().__init__(
            "Pacote de narração inconsistente:\n" + "\n".join(f"- {e}" for e in self.errors)
        )


class NarrationPack(StrictModel):
    """Um pacote de narração: regras de texto por tipo de evento, em JSON."""

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
    errors = [f"referência indefinida em {problem}" for problem in grammar.undefined(roots)]
    cycles = grammar.cycles()
    errors += [f"ciclo entre regras: {cycle}" for cycle in cycles]
    if not cycles:  # sem ciclo o pior caso existe; com ciclo ele não tem fim
        for key, variables in roots.items():
            worst = grammar.worst_length(key, variables)
            if worst > MAX_EXPANDED_CHARS:
                errors.append(
                    f"regra '{key}' pode gerar até {worst} caracteres (limite {MAX_EXPANDED_CHARS}): "
                    "alguma regra se repete demais"
                )
    return errors


def load_pack(data: Any) -> NarrationPack:
    """Valida um pacote (texto JSON ou dicionário) e confere as referências das regras."""
    if isinstance(data, (str, bytes, bytearray)):
        pack = NarrationPack.model_validate_json(data)
    else:
        pack = NarrationPack.model_validate(data)
    errors = validate_pack(pack)
    if errors:
        raise NarrationIntegrityError(errors)
    return pack


def builtin_pack_json(pack_id: str) -> str:
    """O JSON de um pacote de narração embutido; `ValueError` se não existe."""
    resource = resources.files("devaneio.narration").joinpath(f"data/{pack_id}.json")
    if not resource.is_file():
        raise ValueError(f"pacote de narração '{pack_id}' não encontrado")
    return resource.read_text(encoding="utf-8")


def load_builtin_pack(pack_id: str = "pt-br") -> NarrationPack:
    """Carrega e valida um pacote de narração embutido."""
    return load_pack(builtin_pack_json(pack_id))
