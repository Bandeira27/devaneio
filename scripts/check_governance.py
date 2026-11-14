#!/usr/bin/env python3
"""Valida a própria governança: instruções de IA coerentes entre si e sem links quebrados.

Só biblioteca padrão. O risco que este script existe para evitar é a falha silenciosa:
um symlink quebrado ou uma rule órfã deixam a IA sem instrução e ninguém percebe.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = ROOT / ".agents"
errors: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def frontmatter(path: Path) -> dict[str, str]:
    """Lê o bloco `---` inicial (pares chave: valor em uma linha, sem YAML aninhado)."""
    text = path.read_text(encoding="utf-8")
    match = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        fail(f"{rel(path)}: sem frontmatter (--- ... ---)")
        return {}
    pairs = {}
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep:
            pairs[key.strip()] = value.strip()
    return pairs


def check_entrypoints() -> None:
    claude = ROOT / "CLAUDE.md"
    if not (ROOT / "AGENTS.md").is_file():
        fail("AGENTS.md não existe")
    if not claude.is_file() or "@AGENTS.md" not in claude.read_text(encoding="utf-8"):
        fail("CLAUDE.md precisa existir e importar @AGENTS.md (fonte única das instruções)")
    if not (AGENTS_DIR / "README.md").is_file():
        fail(".agents/README.md não existe")


def check_symlinks() -> None:
    for name in ("skills", "agents"):
        link = ROOT / ".claude" / name
        target = AGENTS_DIR / name
        if not link.is_symlink():
            fail(f".claude/{name} deveria ser symlink para ../.agents/{name}")
        elif link.resolve() != target.resolve():
            fail(f".claude/{name} aponta para {link.resolve()}, esperado {target}")


def check_skills() -> None:
    for skill_dir in sorted(p for p in (AGENTS_DIR / "skills").glob("*") if p.is_dir()):
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.is_file():
            fail(f"{rel(skill_dir)}: falta SKILL.md")
            continue
        meta = frontmatter(skill_file)
        if meta.get("name") != skill_dir.name:
            fail(f"{rel(skill_file)}: name deve ser '{skill_dir.name}', veio '{meta.get('name')}'")
        if not meta.get("description"):
            fail(f"{rel(skill_file)}: description vazia")


def check_agents() -> None:
    for agent_file in sorted((AGENTS_DIR / "agents").glob("*.md")):
        meta = frontmatter(agent_file)
        if meta.get("name") != agent_file.stem:
            fail(f"{rel(agent_file)}: name deve ser '{agent_file.stem}', veio '{meta.get('name')}'")
        if not meta.get("description"):
            fail(f"{rel(agent_file)}: description vazia")


def check_rules_are_indexed() -> None:
    agents_md = (
        (ROOT / "AGENTS.md").read_text(encoding="utf-8") if (ROOT / "AGENTS.md").is_file() else ""
    )
    for rule in sorted((AGENTS_DIR / "rules").glob("*.md")):
        if not re.match(r"\d{2}-[a-z0-9-]+\.md$", rule.name):
            fail(f"{rel(rule)}: nome fora do padrão NN-assunto.md")
        if rel(rule) not in agents_md:
            fail(f"{rel(rule)}: rule não referenciada em AGENTS.md (órfã)")


LINK = re.compile(r"\]\((?!https?://|#|mailto:)([^)\s]+)\)")
TICKED_PATH = re.compile(
    r"`((?:\.agents|scripts|\.githooks|contract|backend|frontend|campaigns)/[\w./-]+)`"
)


def check_links() -> None:
    documents = [ROOT / "AGENTS.md", ROOT / "CLAUDE.md", *sorted(AGENTS_DIR.rglob("*.md"))]
    for doc in documents:
        if not doc.is_file():
            continue
        text = doc.read_text(encoding="utf-8")
        for target in LINK.findall(text):
            path = (doc.parent / target.split("#")[0]).resolve()
            if not path.exists():
                fail(f"{rel(doc)}: link quebrado -> {target}")
        for target in TICKED_PATH.findall(text):
            if any(ch in target for ch in "*<>") or target.endswith("/"):
                continue
            if not (ROOT / target).exists():
                fail(f"{rel(doc)}: caminho citado não existe -> {target}")


def main() -> int:
    check_entrypoints()
    check_symlinks()
    check_skills()
    check_agents()
    check_rules_are_indexed()
    check_links()
    for message in errors:
        print(f"governança: {message}", file=sys.stderr)
    if not errors:
        print("governança: ok")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
