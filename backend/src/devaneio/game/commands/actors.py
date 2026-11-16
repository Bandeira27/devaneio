"""Quem age e em quem se age: resolve o personagem, o alvo e se ele pode agir."""

from __future__ import annotations

from devaneio.engine import TargetKind
from devaneio.schema import Character, GameState

from ..session import Session
from .errors import CommandError


def resolve_actor(session: Session, actor: str | None) -> Character:
    characters = session.state.characters
    if actor is not None:
        character = characters.get(actor)
        if character is None:
            raise CommandError(f"personagem '{actor}' não está na partida")
        return character
    if not characters:
        raise CommandError('nenhum personagem na partida; use: entrar <id> "<nome>"')
    if len(characters) == 1:
        return next(iter(characters.values()))
    ids = ", ".join(characters)
    raise CommandError(f"há vários personagens ({ids}); prefixe o comando com `id:`")


def kind_of_target(state: GameState, target_id: str) -> TargetKind:
    is_char, is_npc = target_id in state.characters, target_id in state.npcs
    if is_char and is_npc:
        raise CommandError(f"'{target_id}' é personagem e NPC ao mesmo tempo; ids ambíguos")
    if is_char:
        return "character"
    if is_npc:
        return "npc"
    raise CommandError(f"alvo '{target_id}' não está na partida")


def ensure_can_act(session: Session, character: Character) -> None:
    """Personagem fora de combate (hp 0) não age, a menos que o sistema de regras diga que
    pode (``combat.fallen_can_act``). Morte continua sendo decisão narrativa."""
    if character.hp <= 0 and not session.rules.combat.fallen_can_act:
        raise CommandError(f"{character.name} está fora de combate e não pode agir")
