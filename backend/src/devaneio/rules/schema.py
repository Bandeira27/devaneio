"""Sistema de regras como dados: atributos, dificuldades, habilidades, armas, modificadores.

Fórmulas são strings na linguagem de ``expression.py``. A sintaxe é validada aqui (campo a
campo, pelo Pydantic); os identificadores são conferidos contra os atributos declarados em
``validation.validate_rules``.
"""

from enum import Enum
from typing import Annotated, Literal

from pydantic import AfterValidator, Field, StringConstraints, model_validator

from devaneio.schema.common import Id, StrictModel

from .expression import ExpressionError, parse

# Atributos em maiúsculas para não se confundirem com dados (``d6``) nas fórmulas.
AttrId = Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9_]*$")]


def _check_syntax(text: str) -> str:
    try:
        parse(text)
    except ExpressionError as exc:
        raise ValueError(f"fórmula inválida: {exc}") from None
    return text


Formula = Annotated[str, AfterValidator(_check_syntax)]


class Attribute(StrictModel):
    id: AttrId
    name: str
    description: str = ""
    min: int = 1
    max: int = 5
    default: int = 2

    @model_validator(mode="after")
    def _default_within_range(self) -> "Attribute":
        if not self.min <= self.default <= self.max:
            raise ValueError(f"default ({self.default}) fora do intervalo [{self.min}, {self.max}]")
        return self


class Difficulty(StrictModel):
    id: Id
    name: str
    value: int


class Skill(StrictModel):
    """Habilidade testável. A fórmula é completa (``2d6 + FOR``): sem caso especial no
    interpretador para 'o atributo da habilidade'."""

    id: Id
    name: str
    formula: Formula
    description: str = ""


class Weapon(StrictModel):
    id: Id
    name: str
    damage: Formula
    skill: Id = Field(description="habilidade testada ao atacar com esta arma")
    description: str = ""


class Modifier(StrictModel):
    """Modificador situacional aplicável a qualquer teste (vantagem +2, desvantagem -2)."""

    id: Id
    name: str
    value: int


class CheckOutcome(str, Enum):
    CRITICAL_FAILURE = "critical_failure"
    FAILURE = "failure"
    SUCCESS = "success"
    CRITICAL_SUCCESS = "critical_success"


class Outcomes(StrictModel):
    """Graus de resultado por margem (total - dificuldade). Margem < 0 é falha, >= 0 sucesso;
    os críticos são as caudas."""

    critical_failure_margin: int = Field(description="margem <= este valor é falha crítica")
    critical_success_margin: int = Field(description="margem >= este valor é sucesso crítico")

    @model_validator(mode="after")
    def _thresholds_make_sense(self) -> "Outcomes":
        if not self.critical_failure_margin < 0 < self.critical_success_margin:
            raise ValueError(
                "critical_failure_margin deve ser negativo e critical_success_margin positivo"
            )
        return self


class Combat(StrictModel):
    attack_difficulty: Id = Field(description="dificuldade dos ataques (jogadores e NPCs)")
    default_weapon: Id | None = Field(
        default=None, description="arma de quem não declara nenhuma (NPCs); None exige weapon_id"
    )


class Dispositions(StrictModel):
    hostile_below: int = Field(description="NPC com disposition abaixo disto ataca o grupo")


class Rest(StrictModel):
    heal: Formula = Field(description="hp recuperado por personagem ao descansar")


class RuleSystem(StrictModel):
    schema_version: Literal[1] = 1
    id: Id
    name: str
    description: str = ""
    attributes: list[Attribute] = Field(min_length=1)
    difficulties: list[Difficulty] = Field(min_length=1)
    skills: list[Skill] = Field(min_length=1)
    weapons: list[Weapon] = []
    modifiers: list[Modifier] = []
    outcomes: Outcomes
    combat: Combat
    dispositions: Dispositions
    rest: Rest
    max_hp: Formula = Field(description="fórmula de max_hp na criação do personagem")
