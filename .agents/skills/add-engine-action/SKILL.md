---
name: add-engine-action
description: Use ao criar uma nova ação do motor de regras em backend/src/devaneio/engine/ (nova função que altera o GameState e gera um Event), do código aos testes, documentação e narração.
---

# Adicionar uma ação ao motor

Uma ação é uma **função pura**: recebe estado (e `Campaign`/`RuleSystem` se precisar), devolve resultado
com novo estado e um `Event`. Leia antes `engine/damage.py` e `engine/heal.py` como modelo, e a
[rule 03](../../rules/03-arquitetura.md).

## Passos

1. **Decida se é do motor.** Composição de ações para um comando (como `atacar`) vai em `game/commands/`, não
   aqui. Acerto e dano continuam ações separadas.
2. **Crie o módulo** `engine/<nome>.py`: docstring de módulo curta; `from __future__ import annotations`;
   resultado como `@dataclass(frozen=True)` com `state`, os campos úteis e `text`.
3. **Pureza**: `state.model_copy(deep=True)`; nunca mute a entrada. Aleatoriedade só por
   `Rng(state.rng_seed, state.rng_draws)`, gravando `new_state.rng_draws = rng.draws` (ou `state.rng_draws`
   se não sorteou). Sem I/O, relógio ou `random`.
4. **Erros**: valide e levante `EngineError` com mensagem em pt-br ("npc 'x' está morto..."). Ação que cita
   NPC recebe `campaign` (o nome vem de lá). Use `engine/lookup.py` (`combatant`) em vez de reimplementar busca.
5. **Evento**: `Event(turn=state.turn, kind="<tipo>", text=<linha mecânica pt-br>, data={...})` anexado a
   `new_state.events`.
6. **Exporte** em `engine/__init__.py` (import e `__all__`).
7. **Narração**: um `kind` novo precisa entrar em `EVENT_VARIABLES` (`narration/pack.py`) e ter regras
   `<kind>` / `<kind>.<variante>` em `narration/data/pt-br.json`. O pacote é validado na carga: referência
   indefinida quebra o teste. Sem regra, o evento sai com o texto mecânico (aceitável, mas decida de propósito).
8. **Testes** em `backend/tests/test_<nome>.py` (modelo: `test_damage.py`): pureza (entrada intacta), evento
   (kind, turn, text, data), `rng_draws`, e cada `EngineError` com `match=`. Fixtures de `conftest.py`.
9. **Se mudou algum modelo** (campo novo no estado, em `Event` ou nas regras): skill `change-contract`.
10. **Documentação**: nova linha na tabela "Motor" de `docs/motor.md` (ação, precisa de, evento).
11. `scripts/check` completo verde. Commit atômico `feat: ...` (motor + testes + docs juntos).

## Armadilhas

- Rolar dado fora do `Rng` próprio quebra a reprodutibilidade das partidas salvas.
- Gravar prosa no estado: a narração é gerada na exibição, não guardada.
- Fazer a ação decidir demais (acerto + dano + narração): quem orquestra compõe.
