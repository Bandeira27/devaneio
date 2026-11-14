#!/usr/bin/env python3
"""Nenhuma atribuição de IA em commits, PRs ou código (.agents/rules/06-fluxo-de-trabalho.md).

Preferência do dono do repositório, aplicada por máquina para valer para qualquer IA e
mesmo que a ferramenta insista em acrescentar essas linhas por conta própria.

Modos:
  --message-file F   mensagem de um commit (hook commit-msg)
  --pr-event F       JSON de evento de PR do GitHub (título e corpo; usado no CI)
  (sem argumento)    commits e linhas adicionadas em BASE..HEAD, BASE = CHECK_BASE ou origin/main

Limite: comentários escritos depois na interface do GitHub não passam por aqui.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

TOOLS = (
    r"claude|chatgpt|copilot|codex|gemini|cursor|anthropic|openai|ia|ai|llm|inteligência artificial"
)
PATTERNS = [
    (re.compile(r"^\s*co-authored-by\s*:", re.IGNORECASE | re.MULTILINE), "linha Co-Authored-By"),
    (
        re.compile(rf"generated\s+(with|by)\s+(an?\s+)?({TOOLS})\b", re.IGNORECASE),
        "'Generated with/by <ferramenta>'",
    ),
    (re.compile("\N{ROBOT FACE}"), "emoji de robô"),
    (re.compile(r"noreply@anthropic\.com", re.IGNORECASE), "e-mail de atribuição"),
    (
        re.compile(
            rf"\b(escrit[oa]|criad[oa]|gerad[oa]|written|created|authored|made)\s+"
            rf"(por|com|by|with)\s+(o\s+|a\s+)?({TOOLS})\b",
            re.IGNORECASE,
        ),
        "atribuição a ferramenta/modelo",
    ),
]
# Arquivos de código varridos no diff. Docs e este script descrevem a regra e a citam.
CODE_SUFFIXES = (".py", ".ts", ".js", ".sh", ".yml", ".yaml", ".json")
SKIP_DIFF = {"scripts/check_attribution.py"}


def scan(text: str, origin: str) -> list[str]:
    return [
        f"{origin}: {label} ({match.group(0).strip()!r})"
        for pattern, label in PATTERNS
        for match in [pattern.search(text)]
        if match
    ]


def git(*args: str) -> str | None:
    # Executável e subcomando fixos; só os argumentos variam, e vêm deste próprio script.
    result = subprocess.run(  # noqa: S603 — comando git fixo, sem entrada externa
        ["git", *args],  # noqa: S607 — git resolvido pelo PATH de propósito
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def check_range() -> list[str]:
    base = os.environ.get("CHECK_BASE") or "origin/main"
    if git("rev-parse", "--verify", "-q", base) is None:
        print(f"atribuição: base '{base}' inexistente; varredura de commits ignorada")
        return []
    problems: list[str] = []
    shas = (git("rev-list", f"{base}..HEAD") or "").split()
    for sha in shas:
        message = git("log", "-1", "--format=%B", sha) or ""
        problems += scan(message, f"commit {sha[:8]}")
    diff = git("diff", "--unified=0", f"{base}...HEAD") or ""
    current = ""
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
        elif (
            line.startswith("+")
            and not line.startswith("+++")
            and current.endswith(CODE_SUFFIXES)
            and current not in SKIP_DIFF
        ):
            problems += scan(line[1:], f"{current} (linha adicionada)")
    print(f"atribuição: {len(shas)} commit(s) varridos em {base}..HEAD")
    return problems


def main(argv: list[str]) -> int:
    problems: list[str] = []
    if argv[:1] == ["--message-file"]:
        raw = Path(argv[1]).read_text(encoding="utf-8")
        text = "\n".join(line for line in raw.splitlines() if not line.startswith("#"))
        problems = scan(text, "mensagem do commit")
    elif argv[:1] == ["--pr-event"]:
        event = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        pr = event.get("pull_request") or {}
        problems = scan(pr.get("title") or "", "título da PR") + scan(
            pr.get("body") or "", "corpo da PR"
        )
    else:
        problems = check_range()
    for problem in problems:
        print(f"atribuição: {problem}", file=sys.stderr)
    if problems:
        print(
            "atribuição: remova essas linhas (regra do repositório: nenhuma atribuição de IA).",
            file=sys.stderr,
        )
        return 1
    print("atribuição: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
