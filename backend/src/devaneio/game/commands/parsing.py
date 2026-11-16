"""Análise de uma linha de comando: o prefixo ``id:``, o comando e seus argumentos."""

from __future__ import annotations

import shlex

from .errors import CommandError


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
