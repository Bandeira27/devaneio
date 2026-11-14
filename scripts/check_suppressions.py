#!/usr/bin/env python3
"""Política de supressões (.agents/rules/07-qualidade-e-supressoes.md), aplicada por máquina.

1. Toda supressão inline (`# noqa`, `# type: ignore`) cita o código e traz justificativa
   na mesma linha (` — motivo`) ou num comentário na linha de cima.
2. A configuração das ferramentas não pode enfraquecer em relação à branch base: menos regras
   selecionadas, mais `ignore`/`per-file-ignores`/`exclude`/`omit`, `fail_under` menor,
   mypy sem `strict`. Quem decide aceitar um enfraquecimento é o dono do repositório,
   ao fazer merge de forma consciente; este script só impede que passe despercebido.

Exige Python >= 3.11 (tomllib). Base: variável CHECK_BASE ou origin/main.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import tomllib

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = "backend/pyproject.toml"
errors: list[str] = []

NOQA = re.compile(r"#\s*noqa\b(?P<rest>.*)$", re.IGNORECASE)
TYPE_IGNORE = re.compile(r"#\s*type:\s*ignore\b(?P<rest>.*)$")
JUSTIFIED = re.compile(r"\s—\s*\S")  # travessão com espaços e texto depois


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


def tracked_python_files() -> list[Path]:
    listing = git("ls-files", "*.py") or ""
    return [ROOT / line for line in listing.splitlines() if line]


def check_inline() -> None:
    for path in tracked_python_files():
        if path.name == "check_suppressions.py":
            continue  # este arquivo cita os padrões em regex e docstring
        lines = path.read_text(encoding="utf-8").splitlines()
        for number, line in enumerate(lines, start=1):
            noqa, type_ignore = NOQA.search(line), TYPE_IGNORE.search(line)
            if not noqa and not type_ignore:
                continue
            where = f"{path.relative_to(ROOT)}:{number}"
            if noqa and not re.match(r"\s*:\s*[A-Z]+\d+", noqa.group("rest")):
                errors.append(f"{where}: noqa sem código (use `# noqa: XYZ123 — motivo`)")
            if type_ignore and not re.match(
                r"\s*\[[\w-]+(,\s*[\w-]+)*\]", type_ignore.group("rest")
            ):
                errors.append(f"{where}: type: ignore sem código (use `[código] — motivo`)")
            above = lines[number - 2].strip() if number >= 2 else ""
            if not (JUSTIFIED.search(line) or above.startswith("#")):
                errors.append(
                    f"{where}: supressão sem justificativa (` — motivo` ou comentário acima)"
                )


def facts(text: str) -> dict[str, Any]:
    data = tomllib.loads(text)
    tool = data.get("tool", {})
    ruff = tool.get("ruff", {})
    lint = ruff.get("lint", {})
    coverage = tool.get("coverage", {})
    per_file = {
        (glob, code) for glob, codes in lint.get("per-file-ignores", {}).items() for code in codes
    }
    return {
        "adopted": bool(ruff),
        "fail_under": coverage.get("report", {}).get("fail_under", 0),
        "select": set(lint.get("select", [])),
        "ignore": set(lint.get("ignore", [])),
        "per_file": per_file,
        "excluded": set(ruff.get("exclude", [])) | set(ruff.get("extend-exclude", [])),
        "omit": set(coverage.get("run", {}).get("omit", [])),
        "mypy_strict": bool(tool.get("mypy", {}).get("strict", False)),
    }


def check_config() -> None:
    base = os.environ.get("CHECK_BASE") or "origin/main"
    if git("rev-parse", "--verify", "-q", base) is None:
        print(f"supressões: base '{base}' inexistente; comparação de configuração ignorada")
        return
    old_text = git("show", f"{base}:{PYPROJECT}")
    if old_text is None:
        print("supressões: base sem pyproject; comparação de configuração ignorada")
        return
    old, new = facts(old_text), facts((ROOT / PYPROJECT).read_text(encoding="utf-8"))
    if not old["adopted"]:
        print("supressões: ferramentas ainda não adotadas na base; este é o ponto de partida")
        return

    def weaker(message: str) -> None:
        errors.append(f"configuração enfraquecida em relação a {base}: {message}")

    if new["fail_under"] < old["fail_under"]:
        weaker(f"fail_under {old['fail_under']} -> {new['fail_under']}")
    for key, label in (
        ("ignore", "ruff ignore"),
        ("per_file", "per-file-ignores"),
        ("excluded", "ruff exclude"),
        ("omit", "coverage omit"),
    ):
        added = new[key] - old[key]
        if added:
            weaker(f"{label} ganhou {sorted(map(str, added))}")
    removed = old["select"] - new["select"]
    if removed:
        weaker(f"ruff select perdeu {sorted(removed)}")
    if old["mypy_strict"] and not new["mypy_strict"]:
        weaker("mypy deixou de ser strict")


def main() -> int:
    check_inline()
    check_config()
    for message in errors:
        print(f"supressões: {message}", file=sys.stderr)
    if not errors:
        print("supressões: ok")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
