"""Ações que o LLM pode PROPOR. Nada aqui altera estado: uma proposta válida vira comandos
que passam pelas mesmas funções e validações do motor.

Fora da lista de propósito: dano ou cura de quantia arbitrária (o modelo inventaria
números) e qualquer mudança direta de marcos, que é do diretor.
"""

from __future__ import annotations

import json
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from devaneio.schema.common import Id

MAX_ACTIONS = 3


class _Loose(BaseModel):
    """Saída de LLM: campo extra inofensivo (ex.: "motivo") é ignorado em vez de gastar uma
    tentativa. Campos obrigatórios e ids continuam validados."""

    model_config = ConfigDict(extra="ignore")


class CheckAction(_Loose):
    kind: Literal["check"]
    skill: Id
    difficulty: Id
    modifier: Id | None = None


class AttackAction(_Loose):
    kind: Literal["attack"]
    weapon: Id
    target: Id
    modifier: Id | None = None


class MoveAction(_Loose):
    kind: Literal["move"]
    to: Id


class RestAction(_Loose):
    kind: Literal["rest"]


Action = Annotated[
    Union[CheckAction, AttackAction, MoveAction, RestAction], Field(discriminator="kind")
]


class Proposal(_Loose):
    actions: list[Action] = Field(default_factory=list, max_length=MAX_ACTIONS)
    # Fala do mestre/NPC: só exibida, nunca altera estado.
    say: str = Field(default="", max_length=1000)

    @field_validator("say", mode="before")
    @classmethod
    def _none_is_empty(cls, value):
        return "" if value is None else value


EXAMPLE_PROPOSAL = {
    "actions": [
        {"kind": "check", "skill": "furtividade", "difficulty": "normal", "modifier": None},
        {"kind": "move", "to": "floresta"},
    ],
    "say": "Você some entre as sombras e segue pela trilha.",
}


class ProposalError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


def parse_proposal(raw: str) -> Proposal:
    """Extrai o primeiro objeto JSON da resposta (tolera texto ao redor e cercas de
    markdown) e valida. ``ProposalError`` traz todos os problemas, para virar feedback."""
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
    """Linha de comando do CLI equivalente. Os ids são slugs (validados acima), então não
    há como injetar outro comando ou argumento pela proposta."""
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
