---
name: quality-gate
description: Use para rodar, interpretar e corrigir os portões de qualidade (scripts/check, ruff, mypy, import-linter, pytest com cobertura, Prettier, tsc, contrato), sempre corrigindo a causa e nunca silenciando a ferramenta.
---

# Portões de qualidade

`scripts/check` é a única definição dos portões; hook e CI rodam o mesmo script. Política completa:
[rule 07](../../rules/07-qualidade-e-supressoes.md).

## Rodar

```bash
scripts/check --fast   # lint, formato, tipos, camadas, supressões, Prettier
scripts/check          # completo: + pytest com cobertura, tsc, contrato em dia, atribuição
```

Ambiente ausente? `cd backend && uv venv && uv pip install -e ".[dev]"` e `cd frontend && npm install`.
Um `SKIP` do frontend significa que Prettier, tsc e contrato **não** foram verificados: instale e rode de novo.

## Quando falhar: causa antes de sintoma

| Falha                | Leia a mensagem e...                                                                                    |
| -------------------- | ------------------------------------------------------------------------------------------------------- |
| `ruff format`        | `cd backend && .venv/bin/ruff format . ../scripts --config pyproject.toml`                              |
| `ruff check`         | corrija; `ruff check --fix` só para o que é seguro. Entenda a regra (`ruff rule S310`) antes de agir    |
| `mypy`               | ajuste o **tipo** ou a lógica (estreite `Literal`, discrimine a união). Não use `Any`/`cast` para calar |
| `import-linter`      | o import viola as camadas ([rule 03](../../rules/03-arquitetura.md)); mova o código para a camada certa |
| `pytest` / cobertura | conserte o código ou escreva o teste que falta; nunca baixe `fail_under`                                |
| `contrato em dia`    | rode a skill `change-contract` e commite o regenerado                                                   |
| `supressões`         | complete código + justificativa, ou remova a supressão e corrija a causa                                |
| `atribuição`         | remova a linha de atribuição de IA da mensagem ou do código                                             |
| `governança`         | ajuste a estrutura de `.agents/`, links ou symlinks que o script apontou                                |

## O que fazer com um falso positivo

1. Confirme que é falso positivo (cite a evidência).
2. Supressão **local**, com código e justificativa: `# noqa: S310 — esquema http(s) validado em LlmConfig`.
3. Se o padrão se repete ou a regra está errada para o projeto, **pare e peça ao dono**; não mexa na
   configuração. `check_suppressions.py` falha se a configuração enfraquecer em relação à branch base.
