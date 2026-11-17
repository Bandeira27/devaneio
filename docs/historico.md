# Histórico de etapas

O que cada etapa de construção entregou, em ordem. O que vem a seguir está em [`rumo-extensibilidade.md`](rumo-extensibilidade.md).

- Etapa 1: esquema de dados (`Campaign` estático e `GameState` mutável), validação de integridade e contrato gerado.
- Etapa 2: interpretador de expressões, esquema do sistema de regras com o sistema padrão, RNG reprodutível e `resolve_check` (teste de habilidade que gera novo estado e evento).
- Etapa 3: NPCs com atributos (parciais na campanha, completados pelos defaults do sistema) e `hp` pela fórmula de `max_hp`; `deal_damage` (arma rolada com os atributos do atacante), `apply_damage` (quantia fixa) e `end_turn`. hp tem piso em 0: personagem fica fora de combate, morte é decisão narrativa; NPC fica `alive=false`.
- Etapa 4: `add_character` (atributos parciais completados pelo sistema, hp pela fórmula) e `move` (o grupo anda junto, só por `connections`). Com isso uma partida mínima dá a volta: criar, andar, testar, ferir, encerrar turno.
- Etapa 5: linha de comando (`devaneio.cli`) com partida em disco e interpretador de comandos puro (hoje em `devaneio.game`); `Weapon.skill` no sistema de regras; campanha de exemplo em `campaigns/`.
- Etapa 6: marcos como ações (`activate_beat`, `complete_beat`, `fail_beat`), condições declarativas na campanha (`activate_when`/`complete_when`) e o diretor de narrativa: avança marcos pelos gatilhos, faz NPCs hostis reagirem ao fim do turno e mede a tensão. `combat` e `dispositions` no sistema de regras; `disposition` e `weapon_id` no NPC.
- Etapa 7: narração por gramáticas. Pacote `pt-br` (`backend/src/devaneio/narration/data/pt-br.json`, contrato em `contract/narration.schema.json`) no estilo Tracery; `Narrator.narrate(evento, índice, estado)` gera prosa na exibição, sem gravar no estado e sem consumir `rng_draws`. O CLI mostra a prosa e, abaixo, a linha mecânica entre colchetes.
- Etapa 8: cura e descanso (`heal`, `rest`, com `rest.heal` no sistema de regras), `game_status` (vitória e derrota derivadas do estado, sem campo novo), inventário exigindo a arma em `atacar`, comandos `curar`, `descansar` e `entrar ... +item` no CLI.
- Etapa 9: LLM opcional (`devaneio.llm`). Interpreta texto livre do jogador em ações validadas pelo motor e narra os eventos em prosa, com a gramática como fallback.
- Etapa 10: pacote `game` extraído do CLI; mesa no arquivo de partida (`SaveFile.table`), escrita atômica, `load_game(campaign_root=)`; servidor HTTP (`devaneio.server`, só stdlib) que cria uma mesa a partir do catálogo de campanhas e devolve o estado a quem tem o token.
- Redesenho do app (2026-11): transição entre telas, fundação visual, entrada e mesa em painéis para a tela larga; ver [`design-system.md`](design-system.md) e [`padroes-de-interacao.md`](padroes-de-interacao.md).
