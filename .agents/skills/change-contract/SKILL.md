---
name: change-contract
description: Use quando um modelo Pydantic (schema/, rules/schema.py, narration/pack.py) muda e é preciso regenerar contract/*.schema.json e os tipos TypeScript, e provar que o contrato versionado está em dia.
---

# Mudar o contrato

O contrato é **gerado**: modelos Pydantic → `contract/*.schema.json` → `frontend/src/contract/*.ts`.
Nunca edite os dois últimos à mão.

## Passos

1. Edite o modelo no backend (ids são slugs `Id`; modelos herdam de `StrictModel`, que proíbe campo
   desconhecido). Campo novo com default mutável (`= []`) é aceito nos modelos Pydantic (ver config do ruff).
2. Regenere os JSON Schemas:
   ```bash
   cd backend && .venv/bin/python -m devaneio.export_schema
   ```
3. Regenere os tipos:
   ```bash
   cd frontend && npm run types
   ```
4. Revise `git diff contract frontend/src/contract`: só deve mudar o que você alterou. Mudança inesperada
   indica modelo tocado sem querer ou versão diferente de ferramenta.
5. Se mudou o formato de arquivo persistido (partida, campanha, regras), pense na **compatibilidade**:
   `schema_version` existe nos modelos para isso. Mudança incompatível é decisão do dono: pergunte.
6. Ajuste testes (`tests/test_export_schema.py`, testes do modelo) e `frontend/src/index.ts` se um tipo usado
   mudou (`npm run typecheck`).
7. `scripts/check`: o passo "contrato em dia" regenera e falha se algo mudou. Verde = commit
   (modelos, contrato e tipos juntos, em um commit `feat:`/`fix:`).

## Armadilhas

- Docstring de modelo e `description` de campo entram no contrato: editar só a docstring já muda `contract/` e
  os tipos TS. Regenere e revise o diff como em qualquer mudança de modelo.

- `Campaign` é exportada em modo _validation_ e `GameState` em modo _serialization_ (campos com default
  viram obrigatórios para o cliente): não mude isso sem entender o porquê (`export_schema.py`).
- Títulos por campo são desligados de propósito (evitam `Id1`, `Turn2` nos tipos TS).
