"""Despacho: acha o comando da linha, aplica-o e deixa o diretor reagir ao que mudou."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from devaneio.engine import EngineError, GameStatus, advance_beats, game_status, reveal_facts
from devaneio.schema import GameState

from ..session import Session
from .actions import (
    cmd_attack,
    cmd_beat,
    cmd_check,
    cmd_end_turn,
    cmd_go,
    cmd_heal,
    cmd_hurt,
    cmd_join,
    cmd_rest,
    cmd_reveal,
)
from .errors import READ_ONLY, CommandError, GameOverError
from .parsing import parse_line, split_actor
from .view import cmd_beats, cmd_facts, cmd_help, cmd_log, cmd_look, cmd_sheet

Handler = Callable[[Session, "str | None", list[str]], "tuple[GameState, str]"]

COMMANDS: dict[str, Handler] = {
    "ajuda": cmd_help,
    "olhar": cmd_look,
    "entrar": cmd_join,
    "ir": cmd_go,
    "testar": cmd_check,
    "atacar": cmd_attack,
    "ferir": cmd_hurt,
    "curar": cmd_heal,
    "descansar": cmd_rest,
    "ficha": cmd_sheet,
    "marcos": cmd_beats,
    "marco": cmd_beat,
    "fatos": cmd_facts,
    "revelar": cmd_reveal,
    "log": cmd_log,
    "fim": cmd_end_turn,
}


def is_command(line: str) -> bool:
    """A primeira palavra (depois de um ``id:`` opcional) é um comando conhecido?"""
    _, rest = split_actor(line)
    first = rest.split(maxsplit=1)
    return bool(first) and first[0].lower() in COMMANDS


def execute(session: Session, line: str) -> tuple[Session, str]:
    """Executa uma linha de comando e devolve a nova sessão e o texto.

    ``GameOverError`` (uma ``CommandError``) se a partida acabou e o comando não é de consulta;
    ``CommandError`` para qualquer outra recusa. Linha vazia não faz nada.
    """
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
