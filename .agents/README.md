# Estrutura de instruções para IA

Fonte única do conteúdo; nada aqui é duplicado em outro lugar. Princípios do produto ficam no
[README](../README.md) do repositório, e `AGENTS.md` (raiz) é o ponto de entrada.

```
AGENTS.md              entrada, curta; resume e aponta para o resto
CLAUDE.md              importa AGENTS.md (Claude Code lê CLAUDE.md, não AGENTS.md)
.agents/rules/         normas por assunto, numeradas (NN-assunto.md), lidas sob demanda
.agents/skills/<nome>/SKILL.md   procedimentos recorrentes (formato aberto de skills)
.agents/agents/<papel>.md        papéis de subagente (frontmatter + corpo)
.claude/skills, .claude/agents   symlinks para os dois diretórios acima (Claude Code)
scripts/ e .githooks/  verificações automáticas: a camada que não depende de nenhuma IA
```

## Compatibilidade entre ferramentas

Um núcleo compartilhado **não garante** que cada ferramenta o interprete sozinha. Verificado em
2026-11-13 nas documentações oficiais; "não verificado" significa que a afirmação veio de fonte não oficial
ou não foi reconferida.

| Ferramenta | Lê `AGENTS.md` | Skills (`SKILL.md`) em `.agents/skills` | Nossos agentes (`.agents/agents/*.md`) |
|---|---|---|---|
| Claude Code | não; usa `CLAUDE.md`, que importa o `AGENTS.md` | via symlink `.claude/skills` (não reverificado nesta data) | via symlink `.claude/agents` (não reverificado nesta data) |
| Codex (OpenAI) | sim | sim, procura `.agents/skills` ([docs](https://developers.openai.com/codex/skills)) | não: subagentes são TOML em `.codex/agents/` ([docs](https://developers.openai.com/codex/subagents/)); aplicar como checklist |
| Cursor | sim ([docs](https://cursor.com/docs/rules)) | sim, `.agents/skills` e `.claude/skills` ([docs](https://cursor.com/docs/skills.md)) | sim, lê `.claude/agents` por compatibilidade ([docs](https://cursor.com/docs/subagents)) |
| GitHub Copilot | sim, mas não em todos os recursos ([docs](https://docs.github.com/en/copilot/reference/custom-instructions-support)) | sim, `.agents/skills`, `.claude/skills` ou `.github/skills` ([docs](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills)) | não: agentes próprios em `.github/agents/*.agent.md`; aplicar como checklist |
| Gemini CLI | **não por padrão**: lê `GEMINI.md`; para usar `AGENTS.md` é preciso configurar `context.fileName` ([docs](https://geminicli.com/docs/cli/gemini-md/), [issue](https://github.com/google-gemini/gemini-cli/issues/28227)) | `.agents/skills` (fonte não oficial; não verificado) | não verificado; aplicar como checklist |

Consequências práticas:

- Para ferramentas sem suporte nativo a skills ou subagentes, o `AGENTS.md` manda **ler o arquivo do papel ou
  da skill e aplicar como checklist**; o protocolo de orquestração (rule 08) vale igual.
- O frontmatter `tools:` dos agentes é do Claude Code; as outras ferramentas ignoram a chave e leem o corpo.
- Não mantemos adaptadores por ferramenta (`GEMINI.md`, `.cursor/rules`, `.github/agents`): seria duplicar
  conteúdo. Se uma ferramenta nova for adotada, configure-a para ler `AGENTS.md` (como no Gemini) ou
  acrescente só um arquivo de uma linha apontando para ele, e registre aqui.
- Os symlinks exigem suporte do sistema (Windows precisa de modo desenvolvedor).

## Como evoluir (sem duplicar nem divergir)

- **Nova rule**: um arquivo `NN-assunto.md` em `.agents/rules/`, uma preocupação por arquivo, e uma linha na tabela do `AGENTS.md`.
  `scripts/check_governance.py` falha para rule órfã.
- **Nova skill**: pasta com `SKILL.md`; `name` igual ao nome da pasta e `description` dizendo *quando* usar.
- **Novo papel de subagente**: só se houver tema sem dono; escopo disjunto dos existentes (rule 08, seção
  de sobreposição). `name` igual ao nome do arquivo.
- Afirmação que uma ferramenta já checa (`ruff`, `mypy`, import-linter) **não vira texto aqui**: vira
  configuração. Texto é para o que só julgamento resolve.
- Mudou algo? `scripts/check` valida links, symlinks e frontmatter.
