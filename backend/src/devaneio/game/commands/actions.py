"""Comandos que mudam a partida: entrar, andar, testar, atacar, ferir, curar, descansar, marcos e fatos."""

from __future__ import annotations

from devaneio.engine import (
    HIT,
    activate_beat,
    add_character,
    apply_damage,
    complete_beat,
    deal_damage,
    fail_beat,
    heal,
    move,
    pass_turn,
    resolve_check,
    rest,
    reveal_fact,
)
from devaneio.schema import GameState

from ..session import Session
from .actors import ensure_can_act, kind_of_target, resolve_actor
from .errors import CommandError


def cmd_join(session: Session, _actor: str | None, args: list[str]) -> tuple[GameState, str]:
    """`entrar <id> "<nome>" [FOR=3 ...] [+item ...]`: cria um personagem."""
    if len(args) < 2:
        raise CommandError('uso: entrar <id> "<nome>" [FOR=3 ...] [+item ...]')
    char_id, name, *attr_tokens = args
    attributes: dict[str, int] = {}
    inventory: list[str] = []
    for token in attr_tokens:
        if token.startswith("+"):
            if len(token) == 1:
                raise CommandError("item vazio; use +nome")
            inventory.append(token[1:])
            continue
        key, sep, value = token.partition("=")
        if not sep or not value.lstrip("-").isdigit():
            raise CommandError(f"atributo inválido '{token}'; use NOME=valor")
        attributes[key] = int(value)
    result = add_character(
        session.state,
        session.rules,
        character_id=char_id,
        name=name,
        attributes=attributes,
        inventory=inventory,
    )
    return result.state, result.text


def cmd_go(session: Session, actor: str | None, args: list[str]) -> tuple[GameState, str]:
    """`ir <local>`: move o grupo para um local ligado ao atual."""
    if len(args) != 1:
        raise CommandError("uso: ir <local>")
    if actor is not None:  # o grupo anda junto: só quem é nomeado precisa poder agir
        ensure_can_act(session, resolve_actor(session, actor))
    result = move(session.state, session.campaign, to_location_id=args[0])
    return result.state, result.text


def cmd_check(session: Session, actor: str | None, args: list[str]) -> tuple[GameState, str]:
    """`testar <habilidade> <dificuldade> [modificador]`: teste de habilidade."""
    if len(args) not in (2, 3):
        raise CommandError("uso: testar <habilidade> <dificuldade> [modificador]")
    character = resolve_actor(session, actor)
    ensure_can_act(session, character)
    result = resolve_check(
        session.state,
        session.rules,
        character_id=character.id,
        skill_id=args[0],
        difficulty_id=args[1],
        modifier_id=args[2] if len(args) == 3 else None,
    )
    return result.state, result.text


def cmd_attack(session: Session, actor: str | None, args: list[str]) -> tuple[GameState, str]:
    """`atacar <arma> <alvo> [modificador]`: teste da habilidade da arma e, em acerto, dano."""
    if len(args) not in (2, 3):
        raise CommandError("uso: atacar <arma> <alvo> [modificador]")
    weapon_id, target_id = args[0], args[1]
    character = resolve_actor(session, actor)
    ensure_can_act(session, character)
    weapon = next((w for w in session.rules.weapons if w.id == weapon_id), None)
    if weapon is None:
        raise CommandError(f"arma '{weapon_id}' não existe no sistema de regras")
    target_kind = kind_of_target(session.state, target_id)
    if target_kind == "character" and target_id == character.id:
        raise CommandError("atacar a si mesmo não é permitido")
    always = session.rules.combat.default_weapon
    if weapon_id != always and weapon_id not in character.inventory:
        extra = f" (sempre disponível: {always})" if always else ""
        raise CommandError(f"{character.name} não tem '{weapon_id}' no inventário{extra}")

    check = resolve_check(
        session.state,
        session.rules,
        character_id=character.id,
        skill_id=weapon.skill,
        difficulty_id=session.rules.combat.attack_difficulty,
        modifier_id=args[2] if len(args) == 3 else None,
        attack=True,
    )
    if check.outcome not in HIT:
        return check.state, f"{check.text}\nO ataque não acerta."
    damage = deal_damage(
        check.state,
        session.campaign,
        session.rules,
        attacker_kind="character",
        attacker_id=character.id,
        weapon_id=weapon_id,
        target_kind=target_kind,
        target_id=target_id,
    )
    return damage.state, f"{check.text}\n{damage.text}"


def cmd_hurt(session: Session, _actor: str | None, args: list[str]) -> tuple[GameState, str]:
    """`ferir <alvo> <quantia> ["fonte"]`: dano fixo."""
    if len(args) not in (2, 3) or not args[1].lstrip("-").isdigit():
        raise CommandError('uso: ferir <alvo> <quantia> ["fonte"]')
    target_id = args[0]
    result = apply_damage(
        session.state,
        session.campaign,
        target_kind=kind_of_target(session.state, target_id),
        target_id=target_id,
        amount=int(args[1]),
        source=args[2] if len(args) == 3 else "dano",
    )
    return result.state, result.text


def cmd_heal(session: Session, _actor: str | None, args: list[str]) -> tuple[GameState, str]:
    """`curar <alvo> <quantia> ["fonte"]`: cura fixa; levanta quem estava caído."""
    if len(args) not in (2, 3) or not args[1].lstrip("-").isdigit():
        raise CommandError('uso: curar <alvo> <quantia> ["fonte"]')
    target_id = args[0]
    result = heal(
        session.state,
        session.campaign,
        target_kind=kind_of_target(session.state, target_id),
        target_id=target_id,
        amount=int(args[1]),
        source=args[2] if len(args) == 3 else "cura",
    )
    return result.state, result.text


def cmd_rest(session: Session, _actor: str | None, args: list[str]) -> tuple[GameState, str]:
    """`descansar`: cura o grupo e passa o turno."""
    if args:
        raise CommandError("uso: descansar")
    rested = rest(session.state, session.campaign, session.rules)
    turn = pass_turn(rested.state, session.campaign, session.rules)
    return turn.state, f"{rested.text}\n{turn.text}"


def cmd_end_turn(session: Session, _actor: str | None, _args: list[str]) -> tuple[GameState, str]:
    """`fim`: encerra o turno; o diretor age e os NPCs hostis reagem."""
    result = pass_turn(session.state, session.campaign, session.rules)
    return result.state, result.text


def cmd_beat(session: Session, _actor: str | None, args: list[str]) -> tuple[GameState, str]:
    """`marco ativar|concluir|falhar <id>`: move um marco à mão."""
    actions = {"ativar": activate_beat, "concluir": complete_beat, "falhar": fail_beat}
    if len(args) != 2 or args[0] not in actions:
        raise CommandError("uso: marco ativar|concluir|falhar <id>")
    result = actions[args[0]](session.state, session.campaign, beat_id=args[1])
    return result.state, result.text


def cmd_reveal(session: Session, _actor: str | None, args: list[str]) -> tuple[GameState, str]:
    """`revelar <id>`: torna público um fato da campanha."""
    if len(args) != 1:
        raise CommandError("uso: revelar <id do fato>")
    result = reveal_fact(session.state, session.campaign, fact_id=args[0])
    return result.state, result.text
