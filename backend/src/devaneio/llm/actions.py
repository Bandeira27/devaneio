"""Ações que o LLM pode propor.

Nada aqui altera estado: uma proposta válida vira comandos que passam pelas mesmas funções e
validações do motor.

Fora da lista de propósito: dano ou cura de quantia arbitrária (o modelo inventaria números) e
qualquer mudança direta de marcos, que é do diretor.
"""

from __future__ import annotations

import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from devaneio.schema.common import Id

from .text import clean_text

MAX_ACTIONS = 3


class _Loose(BaseModel):
    """Base das propostas do LLM: ignora campos extras inofensivos.

    Saída de LLM: campo extra inofensivo (ex.: "motivo") é ignorado em vez de gastar uma
    tentativa. Campos obrigatórios e ids continuam validados.
    """

    model_config = ConfigDict(extra="ignore")


class CheckAction(_Loose):
    """Proposta de um teste de habilidade."""

    kind: Literal["check"]
    skill: Id
    difficulty: Id
    modifier: Id | None = None


class AttackAction(_Loose):
    """Proposta de um ataque."""

    kind: Literal["attack"]
    weapon: Id
    target: Id
    modifier: Id | None = None


class MoveAction(_Loose):
    """Proposta de ir a um local."""

    kind: Literal["move"]
    to: Id


class RestAction(_Loose):
    """Proposta de descansar."""

    kind: Literal["rest"]


Action = Annotated[
    CheckAction | AttackAction | MoveAction | RestAction, Field(discriminator="kind")
]


class Proposal(_Loose):
    """O que o LLM propõe: até poucas ações e, opcionalmente, uma fala só de exibição."""

    actions: list[Action] = Field(default_factory=list, max_length=MAX_ACTIONS)
    # Fala do mestre/NPC: só exibida, nunca altera estado.
    say: str = Field(default="", max_length=1000)

    @field_validator("say", mode="before")
    @classmethod
    def _none_is_empty(cls, value: object) -> object:
        return "" if value is None else value

    @field_validator("say", mode="after")
    @classmethod
    def _clean(cls, value: str) -> str:
        return clean_text(value)


EXAMPLE_PROPOSAL = {
    "actions": [
        {"kind": "check", "skill": "furtividade", "difficulty": "normal", "modifier": None},
        {"kind": "move", "to": "floresta"},
    ],
    "say": "Você some entre as sombras e segue pela trilha.",
}


class ProposalError(ValueError):
    """A resposta do LLM não serve como proposta; `errors` lista os problemas."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


def parse_proposal(raw: str) -> Proposal:
    """Extrai e valida a proposta de uma resposta do LLM.

    Extrai o primeiro objeto JSON da resposta (tolera texto ao redor e cercas de markdown) e
    valida. ``ProposalError`` traz todos os problemas, para virar feedback.
    """
    start = raw.find("{")
    if start < 0:
        raise ProposalError(["a resposta não contém um objeto JSON"])
    try:
        data, _ = json.JSONDecoder().raw_decode(raw[start:])
    except ValueError as exc:
        raise ProposalError([f"JSON inválido: {exc}"]) from None
    try:
        return Proposal.model_validate(data)
    except ValidationError as exc:
        raise ProposalError(
            [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
        ) from None


def to_command(action: Action, actor_id: str) -> str:
    """A linha de comando equivalente a uma ação proposta.

    Os ids são slugs (validados acima), então não há como injetar outro comando ou argumento
    pela proposta.
    """
    prefix = f"{actor_id}: "
    if isinstance(action, CheckAction):
        extra = f" {action.modifier}" if action.modifier else ""
        return f"{prefix}testar {action.skill} {action.difficulty}{extra}"
    if isinstance(action, AttackAction):
        extra = f" {action.modifier}" if action.modifier else ""
        return f"{prefix}atacar {action.weapon} {action.target}{extra}"
    if isinstance(action, MoveAction):
        return f"{prefix}ir {action.to}"
    return f"{prefix}descansar"
