"""Texto livre: o LLM PROPÕE ações; cada uma vira um comando e passa pelo mesmo ``execute``.

Tudo ou nada: se qualquer ação da proposta falhar, nada é aplicado, o erro volta ao modelo
como feedback e há mais uma tentativa. Depois disso, o erro vai ao jogador e o estado
não muda.
"""

from __future__ import annotations

import re
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

from .commands import STATUS_LABELS, CommandError, execute, resolve_actor
from .session import Session

MAX_ATTEMPTS = 2
PROPOSER_TEMPERATURE = 0.2
_ACTOR_PREFIX = re.compile(r"^([a-z0-9][a-z0-9_-]*):\s+(.+)$", re.S)


@dataclass(frozen=True)
class FreeformResult:
    session: Session
    say: str  # fala do mestre/NPC; só exibida
    commands: tuple[str, ...]  # o que foi executado, sem o prefixo do ator


def run_freeform(session: Session, text: str) -> FreeformResult:
    """``CommandError`` se não der para aplicar; nesse caso ``session`` segue intacta."""
    if session.llm is None:
        raise CommandError("o LLM não está configurado")
    status = game_status(session.state)
    if status is not GameStatus.ACTIVE:
        raise CommandError(f"a partida terminou ({STATUS_LABELS[status]})")

    text = text.strip()
    actor_id = None
    match = _ACTOR_PREFIX.match(text)
    if match and match.group(1) in session.state.characters:
        actor_id, text = match.group(1), match.group(2)
    character = resolve_actor(session, actor_id)

    messages = build_messages(session.campaign, session.rules, session.state, character.id, text)
    problems: list[str] = []
    for _ in range(MAX_ATTEMPTS):
        try:
            raw = session.llm.complete(messages, json_mode=True, temperature=PROPOSER_TEMPERATURE)
        except LlmError as exc:
            raise CommandError(f"o LLM falhou: {exc}") from None
        try:
            proposal = parse_proposal(raw)
            lines = [to_command(a, character.id) for a in proposal.actions]
            working = session
            for line in lines:
                try:
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
