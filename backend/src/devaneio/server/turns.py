"""Execução de um comando da mesa: política (quem pode, com qual linha), motor e fim de turno.

Funções puras sobre ``Session`` e ``TableMeta``: nada aqui lê ou grava arquivo, nem toma lock.
Quem chama (``TableService``) carrega, chama ``apply`` e grava.
"""

from __future__ import annotations

from dataclasses import dataclass

from devaneio.engine import game_status
from devaneio.game import (
    GameOverError,
    Player,
    Session,
    TableMeta,
    execute,
    parse_line,
    split_actor,
)
from devaneio.schema import GameState

from . import policy
from .errors import ApiFailure
from .models import MAX_NAME, CommandRequest, CommandResult, EventView

MAX_JOIN_ARGS = 30  # id, nome, atributos e itens do `entrar`


@dataclass(frozen=True)
class Plan:
    """O que ``_authorize`` decidiu: o tipo do comando, o personagem que age (só em ações)
    e a linha final que o motor vai executar."""

    kind: policy.Kind | None
    actor: str
    line: str


def prefixed(actor: str, rest: str) -> str:
    return f"{actor}: {rest}"


def events_view(session: Session, since: int) -> list[EventView]:
    state = session.state
    return [
        EventView(
            index=index,
            turn=event.turn,
            kind=event.kind,
            text=event.text,
            prose=session.narrator.narrate(event, index, state),
        )
        for index, event in enumerate(state.events)
        if index >= since
    ]


def apply(
    session: Session,
    table: TableMeta,
    player_id: str,
    player: Player,
    request: CommandRequest,
) -> tuple[CommandResult, Session, TableMeta]:
    state = session.state
    plan = authorize(table, player, request, state)
    before = set(state.characters)
    new_session, text = execute(session, plan.line)
    new_table = table
    turn_ended = False
    if plan.kind == "action":
        new_table = table.model_copy(update={"acted": {**table.acted, plan.actor: state.turn}})
        new_session, text, turn_ended = close_turn_if_all_acted(new_session, new_table, text)
    elif plan.kind == "join":
        new_table = adopt(table, player_id, player, set(new_session.state.characters) - before)
    result = CommandResult(
        revision=len(new_session.state.events),
        events=events_view(new_session, len(state.events)),
        text=text,
        status=game_status(new_session.state),
        turn_ended=turn_ended,
    )
    return result, new_session, new_table


def authorize(table: TableMeta, player: Player, request: CommandRequest, state: GameState) -> Plan:
    """Decide se o jogador pode dar este comando agora e com qual linha final. Nada aqui
    muda a mesa; qualquer recusa levanta antes de ``execute``. Comando que o jogo não
    conhece (``kind`` ``None``) segue direto para o ``execute``, que o recusa com a
    mensagem de sempre."""
    actor, name, args = parse_line(request.line)
    kind = policy.classify(name)
    rest = split_actor(request.line)[1]
    line, who = request.line, ""

    if kind == "host" and player.role != "host":
        raise ApiFailure(403, "forbidden", f"'{name}' é um comando do anfitrião")
    if kind == "action":
        who = acting_character(player, actor)
        check_target(state, player, name, args)
        line = prefixed(who, rest)
        if parse_line(line)[:2] != (who, name):  # a linha remontada diz o mesmo
            raise ApiFailure(400, "bad_request", "linha ambígua")
    elif kind == "join":
        check_join(state, player, args)
        line = rest
    elif kind == "read" and actor is None and player.character_ids:
        line = prefixed(player.character_ids[0], rest)  # `ficha` sem id mostra a sua

    if kind in ("action", "join", "host") and request.revision != len(state.events):
        raise ApiFailure(
            409,
            "stale_revision",
            f"a mesa está na revisão {len(state.events)}, não em {request.revision}: releia",
        )
    if kind == "action" and table.acted.get(who) == state.turn:
        raise ApiFailure(409, "already_acted", f"'{who}' já agiu neste turno")
    return Plan(kind, who, line)


def close_turn_if_all_acted(
    session: Session, table: TableMeta, text: str
) -> tuple[Session, str, bool]:
    if not policy.everyone_acted(table, session.state):
        return session, text, False
    try:
        closed, end_text = execute(session, "fim")
    except GameOverError:
        return session, text, False  # a ação acabou de encerrar a partida: sem turno a fechar
    return closed, f"{text}\n{end_text}", True


def adopt(table: TableMeta, player_id: str, player: Player, created: set[str]) -> TableMeta:
    """Liga o personagem recém-criado ao jogador que deu o ``entrar``."""
    [character_id] = created
    owner = player.model_copy(update={"character_ids": [*player.character_ids, character_id]})
    return table.model_copy(update={"players": {**table.players, player_id: owner}})


def acting_character(player: Player, named: str | None) -> str:
    """O personagem que age. Jogador comum: o seu (o único), nunca o de outro. Anfitrião:
    o que citar, ou o seu se tiver exatamente um. Nunca deixa o motor escolher sozinho,
    porque ``resolve_actor`` sem prefixo pega o único personagem da partida, de quem for."""
    if player.role == "host":
        if named is not None:
            return named
        if len(player.character_ids) == 1:
            return player.character_ids[0]
        raise ApiFailure(422, "actor_required", "diga qual personagem age: `id: comando`")
    if not player.character_ids:
        raise ApiFailure(403, "no_character", "você ainda não tem personagem: use `entrar`")
    if named is None:
        return player.character_ids[0]
    if named not in player.character_ids:
        raise ApiFailure(403, "forbidden", f"'{named}' não é um personagem seu")
    return named


def check_target(state: GameState, player: Player, name: str, args: list[str]) -> None:
    """Jogador comum só ataca quem vê: NPC de outro local responde como alvo inexistente,
    para o ataque não revelar nem ferir quem o ``olhar`` não mostra."""
    if name != "atacar" or player.role == "host" or len(args) < 2:
        return
    npc = state.npcs.get(args[1])
    if npc is not None and npc.location_id != state.current_location_id:
        raise ApiFailure(422, "command_refused", f"alvo '{args[1]}' não está na partida")


def check_join(state: GameState, player: Player, args: list[str]) -> None:
    if player.role != "host" and player.character_ids:
        raise ApiFailure(409, "character_limit", "você já tem um personagem")
    if len(args) > MAX_JOIN_ARGS or any(len(a) > MAX_NAME for a in args):
        raise ApiFailure(
            422,
            "command_refused",
            f"entrar aceita até {MAX_JOIN_ARGS} argumentos de até {MAX_NAME} caracteres",
        )
    if args and args[0] in state.npcs:
        raise ApiFailure(422, "command_refused", f"'{args[0]}' já é o id de um NPC")
