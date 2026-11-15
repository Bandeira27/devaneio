"""Texto livre: o LLM PROPÕE ações; cada uma vira um comando e passa pelo mesmo ``execute``.

Tudo ou nada: se qualquer ação da proposta falhar, nada é aplicado, o erro volta ao modelo
como feedback e há mais uma tentativa. Depois disso, o erro vai ao jogador e o estado
não muda.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from devaneio.engine import GameStatus, game_status
from devaneio.llm import (
    LlmError,
    ProposalError,
    build_messages,
    feedback_message,
    parse_proposal,
    to_command,
)

from .commands import CommandError, GameOverError, execute, resolve_actor, split_actor
from .session import Session

MAX_ATTEMPTS = 2
PROPOSER_TEMPERATURE = 0.2


class LlmUnavailableError(CommandError):
    """O servidor de LLM falhou (rede, HTTP, resposta fora do formato). O estado não muda."""


@dataclass(frozen=True)
class FreeformResult:
    session: Session
    say: str  # fala do mestre/NPC; só exibida
    commands: tuple[str, ...]  # o que foi executado, sem o prefixo do ator


def run_freeform(
    session: Session,
    text: str,
    *,
    actor: str | None = None,
    allow: Callable[[Session, str], None] | None = None,
    hide_events: frozenset[int] = frozenset(),
    include_secrets: bool = True,
) -> FreeformResult:
    """``CommandError`` se não der para aplicar (``GameOverError`` se a partida acabou,
    ``LlmUnavailableError`` se o servidor de LLM falhou); nesse caso ``session`` segue intacta.

    ``actor`` fixa o personagem (quem orquestra por cima já decidiu quem fala; o prefixo do
    texto deixa de valer). ``allow(sessão, linha)`` roda antes de cada ação proposta, com a
    sessão já avançada pelas ações anteriores, e recusa levantando ``CommandError``: a recusa
    volta ao modelo como feedback, como qualquer outra."""
    if session.llm is None:
        raise CommandError("o LLM não está configurado")
    status = game_status(session.state)
    if status is not GameStatus.ACTIVE:
        raise GameOverError(status)

    if actor is None:
        # Prefixo ``id:`` só conta se for um personagem da partida; senão é parte do texto.
        actor, rest = split_actor(text)
        if actor in session.state.characters and rest:
            text = rest
        else:
            actor, text = None, text.strip()
    else:
        text = text.strip()
    character = resolve_actor(session, actor)

    messages = build_messages(
        session.campaign,
        session.rules,
        session.state,
        character.id,
        text,
        hide_events=hide_events,
        include_secrets=include_secrets,
    )
    problems: list[str] = []
    for _ in range(MAX_ATTEMPTS):
        try:
            raw = session.llm.complete(messages, json_mode=True, temperature=PROPOSER_TEMPERATURE)
        except LlmError as exc:
            raise LlmUnavailableError(f"o LLM falhou: {exc}") from None
        try:
            proposal = parse_proposal(raw)
            lines = [to_command(a, character.id) for a in proposal.actions]
            working = session
            for line in lines:
                try:
                    if allow is not None:
                        allow(working, line)
                    working, _ = execute(working, line)
                except CommandError as exc:
                    shown = line.split(": ", 1)[1]
                    raise CommandError(f"ação '{shown}' recusada: {exc}") from None
        except ProposalError as exc:
            problems = exc.errors
        except CommandError as exc:
            problems = [str(exc)]
        else:
            shown_lines = tuple(line.split(": ", 1)[1] for line in lines)
            return FreeformResult(working, proposal.say, shown_lines)
        messages = [*messages, {"role": "assistant", "content": raw}, feedback_message(problems)]
    raise CommandError("o mestre (LLM) não propôs uma ação válida: " + "; ".join(problems))
