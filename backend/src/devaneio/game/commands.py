"""Interpretador de comandos: função pura de (sessão, linha) para (nova sessão, texto).

Quem chama (o laço do CLI, um servidor) só lê, chama ``execute`` e mostra. Tudo que o jogador
pode fazer passa por aqui, então os testes cobrem o jogo inteiro sem terminal.
"""

from __future__ import annotations

import shlex
from collections.abc import Callable
from dataclasses import replace

from devaneio.engine import (
    EngineError,
    GameStatus,
    TargetKind,
    activate_beat,
    add_character,
    advance_beats,
    apply_damage,
    complete_beat,
    deal_damage,
    fail_beat,
    game_status,
    heal,
    move,
    npc_ids_at,
    pass_turn,
    resolve_check,
    rest,
    reveal_fact,
    reveal_facts,
)
from devaneio.rules import CheckOutcome
from devaneio.schema import BeatStatus, Character, GameState

from .session import Session

READ_ONLY = {"ajuda", "olhar", "ficha", "marcos", "fatos", "log"}
STATUS_LABELS = {
    GameStatus.WON: "vitória: todos os marcos foram concluídos",
    GameStatus.LOST: "derrota: todo o grupo caiu",
}

BEAT_LABELS = {
    BeatStatus.PENDING: "pendente",
    BeatStatus.ACTIVE: "ativo",
    BeatStatus.DONE: "concluído",
    BeatStatus.FAILED: "falho",
}

HELP = """\
Comandos (prefixe com `id:` para escolher o personagem quando houver mais de um):
  olhar                                  onde o grupo está, saídas, quem está aqui
  entrar <id> "<nome>" [FOR=3 ...] [+item ...]  novo personagem; omitidos usam o padrão;
                                         +espada põe a espada no inventário
  ir <local>                             mover o grupo para um local conectado
  testar <habilidade> <dificuldade> [modificador]
  atacar <arma> <alvo> [modificador]     teste da habilidade da arma (precisa estar no inventário); acerto fere
  ferir <alvo> <quantia> ["fonte"]       dano fixo (armadilha, queda...)
  curar <alvo> <quantia> ["fonte"]       cura fixa (poção, magia); levanta quem estava caído
  descansar                              recupera hp do grupo (sem hostis por perto) e gasta o turno
  ficha [id]                             atributos, hp e inventário
  marcos                                 marcos da trama e seus estados
  marco ativar|concluir|falhar <id>      mover um marco à mão (o diretor cuida dos gatilhos)
  fatos                                  fatos da campanha, revelados e ocultos
  revelar <id>                           tornar um fato público (o diretor revela os que têm gatilho)
  log [n]                                últimos eventos (padrão 10)
  fim                                    encerrar o turno: o diretor age, NPCs hostis reagem
  ajuda                                  esta lista
  sair                                   fechar (a partida já está salva)"""


class CommandError(ValueError):
    """Comando inválido ou recusado pelo motor. O estado não muda."""


class GameOverError(CommandError):
    """A partida já terminou e o comando não é de consulta. O estado não muda."""

    def __init__(self, status: GameStatus) -> None:
        super().__init__(
            f"a partida terminou ({STATUS_LABELS[status]}); "
            f"só é possível: {', '.join(sorted(READ_ONLY))}"
        )
        self.status = status


Handler = Callable[[Session, "str | None", list[str]], "tuple[GameState, str]"]


def split_actor(line: str) -> tuple[str | None, str]:
    """Separa o prefixo ``id:`` (primeira palavra, sem aspas) do resto da linha.

    É o único analisador do prefixo: comandos, texto livre e quem orquestra por cima
    (CLI, servidor) usam esta regra. Sem shlex, para que aspas soltas em texto livre não
    escondam um comando, e para que ``'id:'`` entre aspas não seja prefixo.
    """
    parts = line.split(maxsplit=1)
    head, rest = (parts[0], parts[1].strip()) if len(parts) == 2 else (line.strip(), "")
    if head.endswith(":") and len(head) > 1:
        return head[:-1], rest
    return None, line.strip()


def parse_line(line: str) -> tuple[str | None, str, list[str]]:
    """``(ator, comando em minúsculas, argumentos)`` de uma linha não vazia; ``CommandError``
    se as aspas não fecham ou se o prefixo vem sem comando."""
    actor, rest = split_actor(line)
    try:
        tokens = shlex.split(rest)
    except ValueError as exc:
        raise CommandError(f"aspas desbalanceadas: {exc}") from None
    if not tokens:
        raise CommandError("prefixo sem comando" if actor else "linha vazia")
    return actor, tokens[0].lower(), tokens[1:]


def is_command(line: str) -> bool:
    """A primeira palavra (depois de um ``id:`` opcional) é um comando conhecido?"""
    _, rest = split_actor(line)
    first = rest.split(maxsplit=1)
    return bool(first) and first[0].lower() in COMMANDS


def execute(session: Session, line: str) -> tuple[Session, str]:
    """``GameOverError`` (uma ``CommandError``) se a partida acabou e o comando não é de
    consulta; ``CommandError`` para qualquer outra recusa. Linha vazia não faz nada."""
    if not line.strip():
        return session, ""
    actor, name, args = parse_line(line)
    handler = COMMANDS.get(name)
    if handler is None:
        raise CommandError(f"comando desconhecido '{name}'; digite 'ajuda'")
    status = game_status(session.state)
    if status is not GameStatus.ACTIVE and name not in READ_ONLY:
        raise GameOverError(status)
    try:
        new_state, text = handler(session, actor, args)
        if new_state is not session.state and name != "fim":
            new_state, beat_texts = advance_beats(new_state, session.campaign)
            new_state, reveal_texts = reveal_facts(new_state, session.campaign)
            text = "\n".join([text, *beat_texts, *reveal_texts])
    except EngineError as exc:
        raise CommandError(str(exc)) from None
    return replace(session, state=new_state), text


# --- comandos ------------------------------------------------------------------


def _help(session: Session, _actor: str | None, _args: list[str]) -> tuple[GameState, str]:
    return session.state, HELP


def _look(session: Session, _actor: str | None, _args: list[str]) -> tuple[GameState, str]:
    state, campaign = session.state, session.campaign
    here = next(loc for loc in campaign.locations if loc.id == state.current_location_id)
    names = {loc.id: loc.name for loc in campaign.locations}
    npc_names = {n.id: n.name for n in campaign.npcs}

    lines = [f"Turno {state.turn} — {here.name} ({here.id})"]
    status = game_status(state)
    if status is not GameStatus.ACTIVE:
        lines.append(f"Partida encerrada — {STATUS_LABELS[status]}.")
    if here.description:
        lines.append(here.description)
    exits = ", ".join(f"{names[c]} ({c})" for c in here.connections) or "nenhuma"
    lines.append(f"Saídas: {exits}")

    hostile_below = session.rules.dispositions.hostile_below
    present = [
        f"{npc_names[npc_id]} ({npc_id}) hp {npc.hp}/{npc.max_hp}"
        + (
            ", fora de combate"
            if not npc.alive
            else ", hostil"
            if npc.disposition < hostile_below
            else ""
        )
        for npc_id, npc in state.npcs.items()
        if npc_id in npc_ids_at(state, here.id)
    ]
    lines.append("Aqui: " + (", ".join(present) if present else "ninguém"))
    titles = {b.id: b.title for b in campaign.beats}
    active = [titles[b] for b, st in state.beats.items() if st is BeatStatus.ACTIVE]
    if active:
        lines.append("Marcos ativos: " + ", ".join(active))
    known = [f.text for f in campaign.facts if f.id in state.revealed_facts]
    if known:
        lines.append("Vocês sabem: " + " ".join(known))

    if state.characters:
        party = ", ".join(_char_line(c) for c in state.characters.values())
    else:
        party = 'ninguém ainda (use: entrar <id> "<nome>" [FOR=3 ...])'
    lines.append("Grupo: " + party)
    return state, "\n".join(lines)


def _join(session: Session, _actor: str | None, args: list[str]) -> tuple[GameState, str]:
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


def _ensure_can_act(session: Session, character: Character) -> None:
    """Personagem fora de combate (hp 0) não age, a menos que o sistema de regras diga que
    pode (``combat.fallen_can_act``). Morte continua sendo decisão narrativa."""
    if character.hp <= 0 and not session.rules.combat.fallen_can_act:
        raise CommandError(f"{character.name} está fora de combate e não pode agir")


def _go(session: Session, actor: str | None, args: list[str]) -> tuple[GameState, str]:
    if len(args) != 1:
        raise CommandError("uso: ir <local>")
    if actor is not None:  # o grupo anda junto: só quem é nomeado precisa poder agir
        _ensure_can_act(session, resolve_actor(session, actor))
    result = move(session.state, session.campaign, to_location_id=args[0])
    return result.state, result.text


def _check(session: Session, actor: str | None, args: list[str]) -> tuple[GameState, str]:
    if len(args) not in (2, 3):
        raise CommandError("uso: testar <habilidade> <dificuldade> [modificador]")
    character = resolve_actor(session, actor)
    _ensure_can_act(session, character)
    result = resolve_check(
        session.state,
        session.rules,
        character_id=character.id,
        skill_id=args[0],
        difficulty_id=args[1],
        modifier_id=args[2] if len(args) == 3 else None,
    )
    return result.state, result.text


def _attack(session: Session, actor: str | None, args: list[str]) -> tuple[GameState, str]:
    if len(args) not in (2, 3):
        raise CommandError("uso: atacar <arma> <alvo> [modificador]")
    weapon_id, target_id = args[0], args[1]
    character = resolve_actor(session, actor)
    _ensure_can_act(session, character)
    weapon = next((w for w in session.rules.weapons if w.id == weapon_id), None)
    if weapon is None:
        raise CommandError(f"arma '{weapon_id}' não existe no sistema de regras")
    target_kind = _target_kind(session.state, target_id)
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
    )
    if check.outcome not in (CheckOutcome.SUCCESS, CheckOutcome.CRITICAL_SUCCESS):
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


def _hurt(session: Session, _actor: str | None, args: list[str]) -> tuple[GameState, str]:
    if len(args) not in (2, 3) or not args[1].lstrip("-").isdigit():
        raise CommandError('uso: ferir <alvo> <quantia> ["fonte"]')
    target_id = args[0]
    result = apply_damage(
        session.state,
        session.campaign,
        target_kind=_target_kind(session.state, target_id),
        target_id=target_id,
        amount=int(args[1]),
        source=args[2] if len(args) == 3 else "dano",
    )
    return result.state, result.text


def _heal(session: Session, _actor: str | None, args: list[str]) -> tuple[GameState, str]:
    if len(args) not in (2, 3) or not args[1].lstrip("-").isdigit():
        raise CommandError('uso: curar <alvo> <quantia> ["fonte"]')
    target_id = args[0]
    result = heal(
        session.state,
        session.campaign,
        target_kind=_target_kind(session.state, target_id),
        target_id=target_id,
        amount=int(args[1]),
        source=args[2] if len(args) == 3 else "cura",
    )
    return result.state, result.text


def _rest(session: Session, _actor: str | None, args: list[str]) -> tuple[GameState, str]:
    if args:
        raise CommandError("uso: descansar")
    rested = rest(session.state, session.campaign, session.rules)
    turn = pass_turn(rested.state, session.campaign, session.rules)
    return turn.state, f"{rested.text}\n{turn.text}"


def _sheet(session: Session, actor: str | None, args: list[str]) -> tuple[GameState, str]:
    if len(args) > 1:
        raise CommandError("uso: ficha [id]")
    character = resolve_actor(session, args[0] if args else actor)
    attrs = ", ".join(f"{k} {v}" for k, v in character.attributes.items())
    inventory = ", ".join(character.inventory) or "vazio"
    return session.state, (
        f"{character.name} ({character.id})\n"
        f"hp {character.hp}/{character.max_hp}\n"
        f"{attrs}\n"
        f"Inventário: {inventory}"
    )


def _log(session: Session, _actor: str | None, args: list[str]) -> tuple[GameState, str]:
    count = 10
    if args:
        if len(args) != 1 or not args[0].isdigit():
            raise CommandError("uso: log [n]")
        count = int(args[0])
    events = session.state.events[-count:] if count else []
    if not events:
        return session.state, "Nenhum evento ainda."
    return session.state, "\n".join(f"[t{e.turn}] {e.text}" for e in events)


def _end_turn(session: Session, _actor: str | None, _args: list[str]) -> tuple[GameState, str]:
    result = pass_turn(session.state, session.campaign, session.rules)
    return result.state, result.text


def _beats(session: Session, _actor: str | None, _args: list[str]) -> tuple[GameState, str]:
    lines = []
    for beat in session.campaign.beats:
        status = session.state.beats[beat.id]
        requires = f" (exige: {', '.join(beat.requires)})" if beat.requires else ""
        lines.append(f"[{BEAT_LABELS[status]}] {beat.title} ({beat.id}){requires}")
    return session.state, "\n".join(lines)


def _beat(session: Session, _actor: str | None, args: list[str]) -> tuple[GameState, str]:
    actions = {"ativar": activate_beat, "concluir": complete_beat, "falhar": fail_beat}
    if len(args) != 2 or args[0] not in actions:
        raise CommandError("uso: marco ativar|concluir|falhar <id>")
    result = actions[args[0]](session.state, session.campaign, beat_id=args[1])
    return result.state, result.text


def _facts(session: Session, _actor: str | None, _args: list[str]) -> tuple[GameState, str]:
    lines = []
    for fact in session.campaign.facts:
        label = "revelado" if fact.id in session.state.revealed_facts else "oculto"
        about = f" sobre {fact.about}" if fact.about else ""
        lines.append(f"[{label}] {fact.text} ({fact.id}){about}")
    return session.state, "\n".join(lines) or "Nenhum fato na campanha."


def _reveal(session: Session, _actor: str | None, args: list[str]) -> tuple[GameState, str]:
    if len(args) != 1:
        raise CommandError("uso: revelar <id do fato>")
    result = reveal_fact(session.state, session.campaign, fact_id=args[0])
    return result.state, result.text


COMMANDS: dict[str, Handler] = {
    "ajuda": _help,
    "olhar": _look,
    "entrar": _join,
    "ir": _go,
    "testar": _check,
    "atacar": _attack,
    "ferir": _hurt,
    "curar": _heal,
    "descansar": _rest,
    "ficha": _sheet,
    "marcos": _beats,
    "marco": _beat,
    "fatos": _facts,
    "revelar": _reveal,
    "log": _log,
    "fim": _end_turn,
}


# --- apoio ---------------------------------------------------------------------


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


def _target_kind(state: GameState, target_id: str) -> TargetKind:
    is_char, is_npc = target_id in state.characters, target_id in state.npcs
    if is_char and is_npc:
        raise CommandError(f"'{target_id}' é personagem e NPC ao mesmo tempo; ids ambíguos")
    if is_char:
        return "character"
    if is_npc:
        return "npc"
    raise CommandError(f"alvo '{target_id}' não está na partida")


def _char_line(c: Character) -> str:
    attrs = " ".join(f"{k} {v}" for k, v in c.attributes.items())
    down = ", fora de combate" if c.hp == 0 else ""
    return f"{c.name} ({c.id}) hp {c.hp}/{c.max_hp}{down} | {attrs}"
