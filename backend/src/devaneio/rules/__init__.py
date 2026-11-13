"""Regras como dados: expressões de dados, esquema do sistema de regras e validação."""

from .expression import DiceRoll, EvalResult, ExpressionError, evaluate, identifiers, parse, roll
from .schema import (
    Attribute,
    CheckOutcome,
    Combat,
    Difficulty,
    Dispositions,
    Modifier,
    Outcomes,
    RuleSystem,
    Skill,
    Weapon,
)
from .validation import (
    RulesIntegrityError,
    builtin_rules_json,
    load_builtin_rules,
    load_rules,
    validate_campaign_against_rules,
    validate_rules,
    validate_state_against_rules,
)

__all__ = [
    "Attribute",
    "CheckOutcome",
    "Combat",
    "DiceRoll",
    "Difficulty",
    "Dispositions",
    "EvalResult",
    "ExpressionError",
    "Modifier",
    "Outcomes",
    "RuleSystem",
    "RulesIntegrityError",
    "Skill",
    "Weapon",
    "builtin_rules_json",
    "evaluate",
    "identifiers",
    "load_builtin_rules",
    "load_rules",
    "parse",
    "roll",
    "validate_campaign_against_rules",
    "validate_rules",
    "validate_state_against_rules",
]
