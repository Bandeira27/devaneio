"""O sistema de regras como a API o entrega: atributos, habilidades, armas e combate."""

from __future__ import annotations

from devaneio.rules import RuleSystem
from devaneio.schema import (
    Id,
    StrictModel,
)


class AttributeInfo(StrictModel):
    """Um atributo, com os limites e o valor padrão."""

    id: str
    name: str
    description: str
    min: int
    max: int
    default: int


class SkillInfo(StrictModel):
    """Uma habilidade, com a fórmula."""

    id: Id
    name: str
    description: str
    formula: str


class DifficultyInfo(StrictModel):
    """Uma dificuldade e o valor que o teste precisa alcançar."""

    id: Id
    name: str
    value: int


class WeaponInfo(StrictModel):
    """Uma arma, com a habilidade e o dano."""

    id: Id
    name: str
    description: str
    skill: Id
    damage: str


class ModifierInfo(StrictModel):
    """Um modificador de teste e o quanto ele soma."""

    id: Id
    name: str
    value: int


class CombatInfo(StrictModel):
    """As regras de combate que mudam o que a tela oferece."""

    default_weapon: Id | None  # arma que ninguém precisa ter no inventário (os punhos)
    fallen_can_act: bool  # personagem com hp 0 ainda pode agir


class RulesView(StrictModel):
    """O sistema de regras como os jogadores precisam dele.

    O catálogo para montar as ações da tela e o formulário de personagem. Regra do sistema é
    dado público; ficam de fora só os campos que a tela não usa (``max_hp``, ``rest``,
    ``outcomes``, ``dispositions``).
    """

    id: Id
    name: str
    description: str
    attributes: list[AttributeInfo]
    skills: list[SkillInfo]
    difficulties: list[DifficultyInfo]
    weapons: list[WeaponInfo]
    modifiers: list[ModifierInfo]
    combat: CombatInfo

    @classmethod
    def of(cls, rules: RuleSystem) -> RulesView:
        """A visão do sistema de regras, derivada do sistema da mesa."""
        return cls(
            id=rules.id,
            name=rules.name,
            description=rules.description,
            attributes=[
                AttributeInfo(
                    id=a.id,
                    name=a.name,
                    description=a.description,
                    min=a.min,
                    max=a.max,
                    default=a.default,
                )
                for a in rules.attributes
            ],
            skills=[
                SkillInfo(id=k.id, name=k.name, description=k.description, formula=k.formula)
                for k in rules.skills
            ],
            difficulties=[
                DifficultyInfo(id=d.id, name=d.name, value=d.value) for d in rules.difficulties
            ],
            weapons=[
                WeaponInfo(
                    id=w.id,
                    name=w.name,
                    description=w.description,
                    skill=w.skill,
                    damage=w.damage,
                )
                for w in rules.weapons
            ],
            modifiers=[ModifierInfo(id=m.id, name=m.name, value=m.value) for m in rules.modifiers],
            combat=CombatInfo(
                default_weapon=rules.combat.default_weapon,
                fallen_can_act=rules.combat.fallen_can_act,
            ),
        )
