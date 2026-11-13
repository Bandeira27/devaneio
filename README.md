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

## Estado atual

Etapa 1: esquema de dados (`Campaign` estático e `GameState` mutável), validação de integridade e contrato gerado. Sem motor de regras, sem LLM, sem interface.
