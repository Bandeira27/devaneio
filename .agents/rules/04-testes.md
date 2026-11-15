# 04. Qualidade e testes

Ferramenta: `pytest` (`backend/tests/`), cobertura de linhas **e ramos** via `pytest-cov`. Rodar:
`cd backend && .venv/bin/pytest -q` (rápido) ou `scripts/check` (com piso de cobertura).

## Critérios mínimos

- **Piso de cobertura 92%** (`fail_under` em `backend/pyproject.toml`; medido 94% na adoção). É uma **catraca**:
  só sobe. Baixá-lo ou adicionar `omit` para passar é proibido ([rule 07](07-qualidade-e-supressoes.md)). Lacunas
  conhecidas e honestas: `cli/__main__.py` (laço interativo), `server/__main__.py` (`serve_forever`) e
  `export_schema.py`.
- Cobertura é consequência, não meta: um teste que executa linha sem verificar comportamento não conta.
- Toda mudança de comportamento traz teste no mesmo commit. **Todo bug ganha um teste de regressão que falha
  antes da correção.**

## Como testar

- `tests/` espelha `src/` (`test_damage.py` para `engine/damage.py`). Testes pela **API pública** do pacote;
  não importe `_privado`.
- **Determinismo**: sementes fixas (`SEED = 99`), nunca relógio nem `random`. Sem rede: o servidor LLM é falso
  (`tests/fakes.py`: `FakeLlmServer`, `ScriptedClient`). O servidor da mesa é testado em processo, na porta 0,
  com tokens injetados (`token_source`), nunca com `secrets` de verdade.
- Fixtures compartilhadas em `tests/conftest.py` (`campaign`, `rules`, `campaign_data`); a campanha de
  `campaigns/sombra-do-vale.json` é a fixture. Não crie campanha de teste paralela sem motivo.
- **Toda ação do motor** testa: pureza (o estado de entrada fica intacto), o `Event` gerado, e `rng_draws`
  (avança só quando há dado). Veja `tests/test_damage.py` como modelo.
- Erros: `pytest.raises(Tipo, match=r"trecho da mensagem")` com `match` explícito.
- Asserções simples e uma por linha (uma falha deve apontar o que quebrou); sem `assert a and b`.
- Não faça mock do motor para testar o CLI: o CLI é testado contra o motor real.

## Prevenção de regressões

- `scripts/check` roda tudo em hook de push e no CI (Python 3.10 e 3.12).
- Contrato desatualizado, camada violada, tipo errado e supressão sem justificativa **quebram a construção**:
  não dependem de revisão humana.
- Mudou comportamento observável de um comando do CLI? Ajuste `README.md` (lista de comandos) no mesmo commit.
