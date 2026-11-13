"""Entrada de um personagem na partida."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from pydantic import ValidationError

from devaneio.rng import Rng
from devaneio.rules import ExpressionError, RuleSystem, evaluate, parse
from devaneio.schema import Character, Event, GameState

from .attributes import resolve_attributes
from .errors import EngineError


@dataclass(frozen=True)
class AddCharacterResult:
    state: GameState
    character: Character
    text: str


def add_character(
    state: GameState,
    rules: RuleSystem,
    *,
    character_id: str,
    name: str,
    attributes: Mapping[str, int] | None = None,
    inventory: Iterable[str] = (),
) -> AddCharacterResult:
    """Atributos parciais completados pelos defaults do sistema (só mín/máx limitam);
    hp = max_hp pela fórmula do sistema, consumindo o Rng do estado se ela tiver dados."""
    if character_id in state.characters:
        raise EngineError(f"personagem '{character_id}' já existe")
    full = resolve_attributes(rules, attributes or {}, f"personagem '{character_id}'")

    rng = Rng(state.rng_seed, state.rng_draws)
    try:
        max_hp = evaluate(parse(rules.max_hp), full, rng).total
    except ExpressionError as exc:
        raise EngineError(f"max_hp de '{character_id}': {exc}") from exc
    if max_hp < 1:
        raise EngineError(f"max_hp de '{character_id}' deu {max_hp}; precisa ser >= 1")

    try:
        character = Character(
            id=character_id, name=name, attributes=full, hp=max_hp, max_hp=max_hp,
            inventory=list(inventory),
        )
    except ValidationError as exc:
        raise EngineError(f"personagem '{character_id}' inválido: {exc}") from exc

    attrs_text = ", ".join(f"{k} {v}" for k, v in full.items())
    text = f"{name} entra na aventura ({attrs_text}; hp {max_hp})."
    new_state = state.model_copy(deep=True)
    new_state.characters[character_id] = character
    new_state.rng_draws = rng.draws
    new_state.events.append(
        Event(
            turn=state.turn,
            kind="character_joined",
            text=text,
            data={"character_id": character_id, "attributes": full, "max_hp": max_hp},
        )
    )
    return AddCharacterResult(new_state, character, text)
