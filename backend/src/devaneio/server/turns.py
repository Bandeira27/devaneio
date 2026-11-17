"""Execução de um comando da mesa: política (quem pode, com qual linha), motor e fim de turno.

Funções puras sobre ``Session`` e ``TableMeta``: nada aqui lê ou grava arquivo, nem toma lock.
Quem chama (``TableService``) carrega, chama ``apply`` e grava.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from devaneio.engine import GameStatus, game_status, npc_ids_at
from devaneio.game import (
    CommandError,
    GameOverError,
    Player,
    Role,
    Session,
    TableMeta,
    execute,
    parse_line,
    split_actor,
)
from devaneio.schema import Campaign, Event, GameState

from . import policy
from .auth import find_player
from .errors import ApiFailure
from .models import MAX_NAME, CommandRequest, CommandResult, EventView, Outcome

MAX_JOIN_ARGS = 30  # id, nome, atributos e itens do `entrar`


@dataclass(frozen=True)
class Plan:
    """O que a autorização decidiu sobre um comando.

    O tipo do comando, o personagem que age (só em ações) e a linha final que o motor vai
    executar.
    """

    kind: policy.Kind | None
    actor: str
    line: str


def prefixed(actor: str, rest: str) -> str:
    """A linha com o prefixo do personagem que age."""
    return f"{actor}: {rest}"


# Quem age ou sofre num evento: pares (tipo, id) nas chaves de ``Event.data``.
PARTICIPANT_KEYS = (
    ("actor_kind", "actor_id"),
    ("attacker_kind", "attacker_id"),
    ("target_kind", "target_id"),
)


def hidden_events(state: GameState, campaign: Campaign) -> frozenset[int]:
    """Índices dos eventos sobre NPC que o grupo não via quando eles aconteceram.

    O local do grupo em cada momento vem de reproduzir os ``move`` desde o início da
    campanha, e o do NPC, do que o próprio evento gravou (``data["npc_locations"]``; evento
    antigo sem o campo usa o local atual do NPC). Assim um evento escondido continua
    escondido depois que o grupo chega ao NPC, mesmo que o NPC se mova: a visão só cresce
    por eventos novos, e quem lê com ``since`` não perde nada.
    """
    here = campaign.start_location_id
    hidden: set[int] = set()
    for index, event in enumerate(state.events):
        if event.kind == "move":
            here = str(event.data["to_location_id"])
        for kind_key, id_key in PARTICIPANT_KEYS:
            if event.data.get(kind_key) != "npc":
                continue
            npc_id = str(event.data.get(id_key))
            recorded = event.data.get("npc_locations", {})
            where = recorded.get(npc_id) if isinstance(recorded, dict) else None
            if where is None and npc_id in state.npcs:
                where = state.npcs[npc_id].location_id  # evento antigo: o local de agora
            if where is not None and where != here:
                hidden.add(index)
    return frozenset(hidden)


def hidden_for(role: Role, session: Session) -> frozenset[int]:
    """Quais eventos o papel não pode ver.

    Nada para o anfitrião (o mestre), os eventos sobre NPC escondido para o jogador comum (o
    texto deles cita nome e hp).
    """
    if role == "host":
        return frozenset()
    return hidden_events(session.state, session.campaign)


_CHECK_OUTCOMES: dict[str, Outcome] = {
    "critical_failure": "critical_failure",
    "failure": "failure",
    "success": "success",
    "critical_success": "critical_success",
}
_ATTACK_OUTCOMES: dict[str, Outcome] = {
    "critical_failure": "critical_miss",
    "failure": "miss",
    "success": "hit",
    "critical_success": "critical_hit",
}


def outcome_of(event: Event) -> Outcome | None:
    """O desfecho do evento para o selo do feed, ou ``None`` se não tem selo.

    É a única coisa de ``data`` que sai daqui: só o grau, nunca rolagem, total ou margem. Um grau
    ausente ou desconhecido vira ``None`` em vez de erro.
    """
    if event.kind == "check":
        table = _ATTACK_OUTCOMES if event.data.get("attack") is True else _CHECK_OUTCOMES
        grade = event.data.get("outcome")
        return table.get(grade) if isinstance(grade, str) else None
    if event.kind == "damage":
        return "incapacitated" if event.data.get("incapacitated") is True else "damage"
    if event.kind == "heal":
        return "heal"
    return None


def events_view(
    session: Session,
    since: int,
    narrations: Mapping[int, str] | None = None,
    *,
    role: Role,
) -> list[EventView]:
    """Os eventos de uma posição em diante que o papel pode ver.

    Eventos de ``since`` em diante que o papel pode ver, cada um com a prosa da gramática e o
    índice original (a lista de um jogador pode ter buracos). ``narrations`` traz o parágrafo do
    LLM por índice de evento, onde houver.
    """
    state = session.state
    cached = narrations or {}
    hidden = hidden_for(role, session)
    return [
        EventView(
            index=index,
            turn=event.turn,
            kind=event.kind,
            text=event.text,
            prose=session.narrator.narrate(event, index, state),
            narration=cached.get(index),
            outcome=outcome_of(event),
        )
        for index, event in enumerate(state.events)
        if index >= since and index not in hidden
    ]


def apply(
    session: Session,
    table: TableMeta,
    player_id: str,
    player: Player,
    request: CommandRequest,
) -> tuple[CommandResult, Session, TableMeta]:
    """Executa um comando de um jogador sobre a partida e devolve o resultado, a nova sessão e a mesa."""
    state = session.state
    plan = resolve(player, request.line, state)
    check_turn(table, state, plan, request.revision)
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
        events=events_view(new_session, len(state.events), role=player.role),
        text=text,
        status=game_status(new_session.state),
        turn_ended=turn_ended,
    )
    return result, new_session, new_table


def authenticate(session: Session, token: str) -> tuple[TableMeta, str, Player]:
    """A mesa da partida e o jogador dono do token.

    404 se a partida não é uma mesa, 401 se o token não é de ninguém.
    """
    table = session.table
    if table is None:
        raise ApiFailure(404, "table_not_found", "mesa não encontrada")
    found = find_player(table, token)
    if found is None:
        raise ApiFailure(401, "unauthorized", "token inválido")
    return table, found[0], found[1]


def resolve(player: Player, line: str, state: GameState) -> Plan:
    """Decide se o jogador pode dar o comando e com qual linha.

    Confere papel, personagem que age, alvo visível e limites do ``entrar``. Não olha revisão nem turno (isso é ``check_turn``) e
    não muda nada. Comando que o jogo não conhece (``kind`` ``None``) segue direto para o
    ``execute``, que o recusa com a mensagem de sempre. A linha final é remontada com o prefixo
    do personagem, e ``parse_line`` a lê de volta como (ator, comando) esperados: classificação
    e motor usam o mesmo analisador.
    """
    actor, name, args = parse_line(line)
    kind = policy.classify(name)
    rest = split_actor(line)[1]
    final, who = line, ""

    if kind == "host" and player.role != "host":
        raise ApiFailure(403, "forbidden", f"'{name}' é um comando do anfitrião")
    if kind == "action":
        who = acting_character(player, actor)
        check_target(state, player, name, args)
        final = prefixed(who, rest)
    elif kind == "join":
        check_join(state, player, args)
        final = rest
    elif kind == "read" and actor is None and player.character_ids:
        final = prefixed(player.character_ids[0], rest)  # `ficha` sem id mostra a sua
    return Plan(kind, who, final)


def check_turn(table: TableMeta, state: GameState, plan: Plan, seen: int) -> None:
    """Confere o momento da mesa: revisão e uma ação por turno.

    A revisão que o cliente viu (só para quem muda a partida) e uma ação principal por
    personagem por turno.
    """
    if plan.kind in ("action", "join", "host") and seen != len(state.events):
        raise _stale(state, seen)
    if plan.kind == "action" and table.acted.get(plan.actor) == state.turn:
        raise ApiFailure(409, "already_acted", f"'{plan.actor}' já agiu neste turno")


def check_say(table: TableMeta, state: GameState, who: str, seen: int) -> None:
    """Texto livre: revisão, partida em andamento e ação principal ainda não gasta."""
    if seen != len(state.events):
        raise _stale(state, seen)
    status = game_status(state)
    if status is not GameStatus.ACTIVE:
        raise ApiFailure(409, "game_over", str(GameOverError(status)))
    if table.acted.get(who) == state.turn:
        raise ApiFailure(409, "already_acted", f"'{who}' já agiu neste turno")


def _stale(state: GameState, seen: int) -> ApiFailure:
    current = len(state.events)
    return ApiFailure(
        409, "stale_revision", f"a mesa está na revisão {current}, não em {seen}: releia"
    )


def speaker(state: GameState, player: Player, text: str) -> tuple[str, str]:
    """Quem fala e o texto sem o prefixo de personagem.

    Jogador comum fala pelo seu personagem (prefixo alheio é 403); o anfitrião cita o personagem
    ou usa o seu, se for um só.
    """
    named, rest = split_actor(text)
    if named in state.characters and rest:
        return acting_character(player, named), rest
    return acting_character(player, None), text


def close_turn_if_all_acted(
    session: Session, table: TableMeta, text: str
) -> tuple[Session, str, bool]:
    """Encerra o turno automaticamente quando todos os personagens ligados a jogadores já agiram."""
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
    """O personagem que age.

    Jogador comum: o seu (o único), nunca o de outro. Anfitrião: o que citar, ou o seu se tiver
    exatamente um. Nunca deixa o motor escolher sozinho, porque ``resolve_actor`` sem prefixo
    pega o único personagem da partida, de quem for.
    """
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
    """Confere que o jogador comum só ataca quem ele vê.

    NPC de outro local responde como alvo inexistente, para o ataque não revelar nem ferir quem
    o ``olhar`` não mostra.
    """
    if name != "atacar" or player.role == "host" or len(args) < 2:
        return
    npc_id = args[1]
    if npc_id in state.npcs and npc_id not in npc_ids_at(state, state.current_location_id):
        raise ApiFailure(422, "command_refused", f"alvo '{args[1]}' não está na partida")


def check_join(state: GameState, player: Player, args: list[str]) -> None:
    """Confere os limites do `entrar`: um personagem por jogador e tamanhos dos argumentos."""
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


def authorize_proposal(player: Player, working: Session, line: str) -> None:
    """Aplica a mesma política do jogador a uma ação proposta pelo LLM.

    Uma ação que o LLM propôs passa pela mesma política do jogador que falou: papel, dono do
    personagem, alvo visível. O que não é ação de jogo (leitura, ``entrar``) nem existe como
    proposta. Recusa como ``CommandError``, que vira feedback ao modelo. Revisão e turno já
    foram conferidos para o texto inteiro, não por ação.
    """
    _, name, _ = parse_line(line)
    if policy.classify(name) not in ("action", "host"):
        raise CommandError(f"'{name}' não é uma ação que o mestre possa propor")
    try:
        resolve(player, line, working.state)
    except ApiFailure as exc:
        raise CommandError(exc.message) from None
