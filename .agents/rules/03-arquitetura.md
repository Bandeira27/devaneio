# 03. Governança arquitetural

## Camadas (verificadas por import-linter, `scripts/check`)

```
cli | server                   I/O (terminal; HTTP com a política da mesa) por cima de game; não se importam
game                           orquestração: partida (em memória e em arquivo, sem saber de banco), comandos, texto livre, saída, mesa
engine | narration | llm       irmãos: não se importam entre si
rules                          sistema de regras e expressões (dados interpretados)
schema | rng                   modelos Pydantic e gerador reprodutível
```

Dependências só apontam para baixo. `game` reexporta o que `cli` e `server` precisam de `llm` (`LlmConfig`,
`LlmError`, `ChatClient`): os dois só falam com `game`. `llm/` não conhece o motor: a proposta do modelo vira **linhas de comando**
e passa por `execute()` (`game/commands/`), reaproveitando as validações. `export_schema.py` é ferramenta de
build, no topo: importa `server.models` para exportar o contrato da API, e `server/__init__.py` não reexporta o
adaptador HTTP (`server/http.py`), para a ferramenta de build não carregar `http.server`.
Se uma mudança parece exigir quebrar o contrato de camadas, o desenho está errado ou a decisão é do dono:
pare e pergunte, não ajuste o contrato.

## Onde colocar código novo

O que cabe dentro de um arquivo (uma responsabilidade por módulo) está na [rule 09](09-responsabilidades.md).

| É...                                                                                                                                                                                                                                                                                                                                                                                                                  | Vai em                                                                                                                                |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| ação que altera o estado do jogo                                                                                                                                                                                                                                                                                                                                                                                      | `engine/` (função pura; skill `add-engine-action`)                                                                                    |
| composição de ações para um comando (`atacar` = check + dano)                                                                                                                                                                                                                                                                                                                                                         | `game/commands/actions.py`                                                                                                            |
| modelo persistido fora do contrato (`SaveFile`, `TableMeta`)                                                                                                                                                                                                                                                                                                                                                          | `game/`                                                                                                                               |
| leitura e impressão no terminal                                                                                                                                                                                                                                                                                                                                                                                       | `cli/`                                                                                                                                |
| rota HTTP, política da mesa (papéis: `server/policy.py`; execução de um comando: `server/turns.py`; texto livre pelo LLM: `server/say.py`; persistência das mesas no banco SQLite (SQLAlchemy só aqui: `server/storage.py`, `server/records.py`, `server/database.py`); narração e mural do LLM, só em memória e fora do estado e do banco: `server/presentation.py`; tokens, limites), modelo de requisição/resposta | `server/`                                                                                                                             |
| campo ou modelo de dados                                                                                                                                                                                                                                                                                                                                                                                              | `schema/` ou `rules/schema.py`, depois regenerar o contrato                                                                           |
| fórmula, dificuldade, arma, habilidade                                                                                                                                                                                                                                                                                                                                                                                | arquivo de regras (`rules/data/default.json`), não código                                                                             |
| texto de narração                                                                                                                                                                                                                                                                                                                                                                                                     | pacote pt-br (`narration/data/pt-br.json`), regra `tipo.variante`                                                                     |
| qualquer coisa que fale com o LLM                                                                                                                                                                                                                                                                                                                                                                                     | `llm/` (propõe e valida a saída; nunca altera estado); quem o liga ao jogo (`connect_llm`, `narrate_batch`, `run_freeform`) é `game/` |

## Preservar o que existe

- Leia os vizinhos e siga o padrão antes de criar um novo; um segundo jeito de fazer a mesma coisa é dívida.
- Uma **ação do motor é função pura**: recebe `GameState` (e `Campaign`/`RuleSystem` se precisar), devolve novo
  estado com `rng_draws` coerente e um `Event` no log; **nunca** muta a entrada, faz I/O, lê relógio ou usa
  `random`. Ações que citam NPC recebem `campaign` (o nome vem de lá).
- Acerto e dano são ações separadas; quem orquestra compõe. Não funda isso no motor.
- Soluções improvisadas (flag global, estado em módulo, `try/except` para dirigir fluxo, atalho que pula a
  validação) são rejeitadas mesmo que passem nos testes.

## Dependências

- Runtime hoje: **só `pydantic`**. O cliente LLM e o servidor HTTP (`http.server`) usam a biblioteca padrão por decisão. Nova dependência de runtime
  exige: necessidade que a stdlib não cobre, alternativa considerada, custo de manutenção, e **aprovação do dono**.
- Dependência de desenvolvimento só entra se for usada por `scripts/check`. Intervalos de versão seguem
  `pyproject.toml`/`package.json`; o `ruff` é fixado na versão menor porque o formatador muda entre menores.
- Frontend: sem biblioteca de UI ou framework até o dono abrir esse escopo.

## Contrato

`contract/*.schema.json` e `frontend/src/contract/*.ts` são **gerados**: não edite à mão. Mudou modelo
Pydantic → skill `change-contract`. `scripts/check` falha se o contrato versionado não for o que os modelos geram.
O frontend só consome o contrato; a regra do jogo nunca vai para lá.
