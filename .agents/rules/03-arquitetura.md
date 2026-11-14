# 03. Governança arquitetural

## Camadas (verificadas por import-linter, `scripts/check`)

```
cli                            único que junta tudo (comandos, partida em disco, I/O)
engine | narration | llm       irmãos: não se importam entre si
rules                          sistema de regras e expressões (dados interpretados)
schema | rng                   modelos Pydantic e gerador reprodutível
```

Dependências só apontam para baixo. `llm/` não conhece o motor: a proposta do modelo vira **comandos do CLI**
e passa por `execute()`, reaproveitando as validações. `export_schema.py` é ferramenta de build, no topo.
Se uma mudança parece exigir quebrar o contrato de camadas, o desenho está errado ou a decisão é do dono:
pare e pergunte, não ajuste o contrato.

## Onde colocar código novo

| É... | Vai em |
|---|---|
| ação que altera o estado do jogo | `engine/` (função pura; skill `add-engine-action`) |
| composição de ações para um comando (`atacar` = check + dano) | `cli/commands.py` |
| campo ou modelo de dados | `schema/` ou `rules/schema.py`, depois regenerar o contrato |
| fórmula, dificuldade, arma, habilidade | arquivo de regras (`rules/data/default.json`), não código |
| texto de narração | pacote pt-br (`narration/data/pt-br.json`), regra `tipo.variante` |
| qualquer coisa que fale com o LLM | `llm/` (propõe e valida a saída; nunca altera estado) |

## Preservar o que existe

- Leia os vizinhos e siga o padrão antes de criar um novo; um segundo jeito de fazer a mesma coisa é dívida.
- Uma **ação do motor é função pura**: recebe `GameState` (e `Campaign`/`RuleSystem` se precisar), devolve novo
  estado com `rng_draws` coerente e um `Event` no log; **nunca** muta a entrada, faz I/O, lê relógio ou usa
  `random`. Ações que citam NPC recebem `campaign` (o nome vem de lá).
- Acerto e dano são ações separadas; quem orquestra compõe. Não funda isso no motor.
- Soluções improvisadas (flag global, estado em módulo, `try/except` para dirigir fluxo, atalho que pula a
  validação) são rejeitadas mesmo que passem nos testes.

## Dependências

- Runtime hoje: **só `pydantic`**. O cliente LLM usa a biblioteca padrão por decisão. Nova dependência de runtime
  exige: necessidade que a stdlib não cobre, alternativa considerada, custo de manutenção, e **aprovação do dono**.
- Dependência de desenvolvimento só entra se for usada por `scripts/check`. Intervalos de versão seguem
  `pyproject.toml`/`package.json`; o `ruff` é fixado na versão menor porque o formatador muda entre menores.
- Frontend: sem biblioteca de UI ou framework até o dono abrir esse escopo.

## Contrato

`contract/*.schema.json` e `frontend/src/contract/*.ts` são **gerados**: não edite à mão. Mudou modelo
Pydantic → skill `change-contract`. `scripts/check` falha se o contrato versionado não for o que os modelos geram.
O frontend só consome o contrato; a regra do jogo nunca vai para lá.
