# Devaneio

Mesa de RPG com um mestre de IA, jogável sozinho ou em grupo (por turnos).

## Princípios

- **O motor de regras vive só no backend.** É a fonte da verdade; o frontend é um cliente fino que mostra o estado e envia ações.
- **Estado é dado puro (JSON), em turnos, com fonte única da verdade.**
- **O LLM é opcional e só propõe.** O jogo funciona sem ele (narração por templates e gramáticas). Quando existe, toda mudança de estado passa por chamadas estruturadas validadas pelo motor. Local-first: a chave do usuário nunca sai da máquina dele para um servidor nosso.
- **Regras são dados, não código.** Sistemas de regras são arquivos declarativos interpretados pelo motor. Código enviado pelo usuário nunca é executado.
- **Contrato único.** Os modelos Pydantic geram o JSON Schema em `contract/`, de onde saem os tipos TypeScript.

## Estrutura

```
backend/    Python (Pydantic v2, pytest) — esquema, motor, validação
frontend/   TypeScript strict — cliente fino (por enquanto só esqueleto)
contract/   JSON Schema gerado a partir do backend
```

## Backend

```bash
cd backend
uv venv && uv pip install -e ".[dev]"
.venv/bin/pytest -q
.venv/bin/python -m devaneio.export_schema   # regenera contract/
```

Compatível com Python >= 3.10.

## Frontend

```bash
cd frontend
npm install
npm run types        # gera src/contract/*.ts a partir de ../contract/*.json
npm run typecheck
```

## Sistema de regras

Um sistema é um arquivo JSON (`contract/rules.schema.json`) com atributos, dificuldades,
habilidades, armas, modificadores e graus de resultado. Fórmulas são expressões de dados
interpretadas pelo motor, nunca código:

```
expr   := term (("+" | "-") term)*
term   := factor ("*" factor)*
factor := INT | DICE | IDENT | "(" expr ")" | "-" factor
DICE   := INT? "d" INT          (2d6, d20)
IDENT  := [A-Z][A-Z0-9_]*       (id de atributo)
```

O sistema padrão, **Devaneio Básico** (`backend/src/devaneio/rules/data/default.json`):
atributos FOR, AGI, MEN e PRE de 1 a 5; teste `2d6 + atributo` contra uma dificuldade
(Fácil 7, Normal 9, Difícil 11, Heroica 13); margem ≤ -5 é falha crítica, ≥ 5 sucesso
crítico; vantagem/desvantagem ±2; `max_hp = 6 + FOR * 2`.

A aleatoriedade é reprodutível: o estado guarda só `rng_seed` e `rng_draws`, e o gerador
(SplitMix64 próprio) é recriado a partir deles a cada ação.

## Estado atual

- Etapa 1: esquema de dados (`Campaign` estático e `GameState` mutável), validação de integridade e contrato gerado.
- Etapa 2: interpretador de expressões, esquema do sistema de regras com o sistema padrão, RNG reprodutível e `resolve_check` (teste de habilidade que gera novo estado e evento).

Sem LLM, sem multiplayer, sem interface.
