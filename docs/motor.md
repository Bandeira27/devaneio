# Motor e diretor de narrativa

As ações do motor, o diretor de narrativa e os detalhes dos comandos do CLI.

O arquivo da partida é salvo (de forma atômica) após cada ação e é a fonte da verdade. `atacar` compõe em `game/commands/`
um `resolve_check` (habilidade da arma contra a dificuldade de ataque do sistema) e, em acerto, um `deal_damage`. A arma precisa estar no inventário; a arma padrão do sistema (`combat.default_weapon`) está sempre disponível.

A partida termina em **vitória** (todos os marcos concluídos) ou **derrota** (todo o grupo com hp 0). O desfecho é derivado do estado por `game_status`; o motor não se recusa a agir, e `game/commands/` trava as ações exceto consulta. `descansar` recupera hp pela fórmula `rest.heal`, só sem hostis vivos no local, e gasta o turno.

## Motor

Toda ação do motor (`backend/src/devaneio/engine/`) é uma função pura: recebe `GameState`
(e, quando precisa, `Campaign` e `RuleSystem`), devolve um novo estado com `rng_draws`
avançado e um `Event` no log. O estado de entrada nunca é alterado. O acerto de um ataque
é um `resolve_check`; o dano é um `deal_damage` separado, para quem orquestra decidir.

| Ação                                            | Precisa de          | Evento                                          |
| ----------------------------------------------- | ------------------- | ----------------------------------------------- |
| `initial_state`                                 | campanha, regras    | —                                               |
| `add_character`                                 | regras              | `character_joined`                              |
| `move`                                          | campanha            | `move`                                          |
| `resolve_check`                                 | regras              | `check`                                         |
| `deal_damage` / `apply_damage`                  | campanha (+ regras) | `damage`                                        |
| `heal` / `rest`                                 | campanha (+ regras) | `heal` / `rest`                                 |
| `activate_beat` / `complete_beat` / `fail_beat` | campanha            | `beat_activated` / `beat_done` / `beat_failed`  |
| `direct` / `pass_turn`                          | campanha, regras    | `director` (+ os eventos das ações que dispara) |
| `reveal_facts` / `reveal_fact`                  | campanha            | `reveal`                                        |
| `end_turn`                                      | —                   | `turn_end`                                      |

## Diretor de narrativa

Determinístico, sem LLM, em `backend/src/devaneio/engine/director.py`. Ao fim de cada turno
(`pass_turn`) ele: (1) avança marcos cujas condições declaradas na campanha valem;
(2) faz cada NPC hostil (disposição abaixo de `dispositions.hostile_below`) presente no local
atacar um personagem de pé, com a habilidade da arma contra `combat.attack_difficulty`;
(3) avança marcos de novo (um NPC caído pode concluir algo); (4) mede a **tensão** (0 a 1,
a partir de hp perdido, hostis presentes, caídos e marcos falhos) e registra um evento
`director`. A tensão é derivada e, por enquanto, só observada: usá-la para ritmo é trabalho
futuro. O diretor nunca inventa texto; só dispara ações do motor.

Condições disponíveis nos marcos e nos fatos: `at_location`, `npc_down`, `beat_done`, `turn_at_least` e
`check_passed` (algum personagem passou num teste da habilidade; teste de NPC não conta).
Um marco sem `complete_when` só conclui por ação explícita (`marco concluir <id>` no CLI).

A **fase da mesa** (sala de espera, em andamento, pausada, encerrada) não é do motor: vive em `TableMeta` (`game/`), e quem a muda é `game/lifecycle.py`, que só compõe o motor (a abertura da história roda ao iniciar). O desfecho derivado (`game_status`) segue sendo outro eixo.
