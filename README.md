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

## Jogar (linha de comando)

```bash
cd backend
uv venv && uv pip install -e ".[dev]"
.venv/bin/python -m devaneio.cli nova ../campaigns/sombra-do-vale.json partida.json
.venv/bin/python -m devaneio.cli jogar partida.json
```

Comandos: `olhar`, `entrar <id> "<nome>" [FOR=3 ...]`, `ir <local>`, `testar <habilidade>
<dificuldade> [modificador]`, `atacar <arma> <alvo> [modificador]`, `ferir <alvo> <quantia>`,
`ficha`, `marcos`, `marco ativar|concluir|falhar <id>`, `log`, `fim`, `ajuda`, `sair`. Com mais de um personagem, prefixe: `aria: testar lutar normal`.
O arquivo da partida é salvo após cada ação e é a fonte da verdade. `atacar` compõe no CLI
um `resolve_check` (habilidade da arma contra Normal) e, em acerto, um `deal_damage`.

## Backend

```bash
cd backend
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
- Etapa 3: NPCs com atributos (parciais na campanha, completados pelos defaults do sistema) e `hp` pela fórmula de `max_hp`; `deal_damage` (arma rolada com os atributos do atacante), `apply_damage` (quantia fixa) e `end_turn`. hp tem piso em 0: personagem fica fora de combate, morte é decisão narrativa; NPC fica `alive=false`.
- Etapa 4: `add_character` (atributos parciais completados pelo sistema, hp pela fórmula) e `move` (o grupo anda junto, só por `connections`). Com isso uma partida mínima dá a volta: criar, andar, testar, ferir, encerrar turno.
- Etapa 5: linha de comando (`devaneio.cli`) com partida em disco e interpretador de comandos puro; `Weapon.skill` no sistema de regras; campanha de exemplo em `campaigns/`.
- Etapa 6: marcos como ações (`activate_beat`, `complete_beat`, `fail_beat`), condições declarativas na campanha (`activate_when`/`complete_when`) e o diretor de narrativa: avança marcos pelos gatilhos, faz NPCs hostis reagirem ao fim do turno e mede a tensão. `combat` e `dispositions` no sistema de regras; `disposition` e `weapon_id` no NPC.

## Motor

Toda ação do motor (`backend/src/devaneio/engine/`) é uma função pura: recebe `GameState`
(e, quando precisa, `Campaign` e `RuleSystem`), devolve um novo estado com `rng_draws`
avançado e um `Event` no log. O estado de entrada nunca é alterado. O acerto de um ataque
é um `resolve_check`; o dano é um `deal_damage` separado, para quem orquestra decidir.

| Ação | Precisa de | Evento |
|---|---|---|
| `initial_state` | campanha, regras | — |
| `add_character` | regras | `character_joined` |
| `move` | campanha | `move` |
| `resolve_check` | regras | `check` |
| `deal_damage` / `apply_damage` | campanha (+ regras) | `damage` |
| `activate_beat` / `complete_beat` / `fail_beat` | campanha | `beat_activated` / `beat_done` / `beat_failed` |
| `direct` / `pass_turn` | campanha, regras | `director` (+ os eventos das ações que dispara) |
| `end_turn` | — | `turn_end` |

## Diretor de narrativa

Determinístico, sem LLM, em `backend/src/devaneio/engine/director.py`. Ao fim de cada turno
(`pass_turn`) ele: (1) avança marcos cujas condições declaradas na campanha valem;
(2) faz cada NPC hostil (disposição abaixo de `dispositions.hostile_below`) presente no local
atacar um personagem de pé, com a habilidade da arma contra `combat.attack_difficulty`;
(3) avança marcos de novo (um NPC caído pode concluir algo); (4) mede a **tensão** (0 a 1,
a partir de hp perdido, hostis presentes, caídos e marcos falhos) e registra um evento
`director`. A tensão é derivada e, por enquanto, só observada: usá-la para ritmo é trabalho
futuro. O diretor nunca inventa texto; só dispara ações do motor.

Condições disponíveis nos marcos: `at_location`, `npc_down`, `beat_done`, `turn_at_least`.
Um marco sem `complete_when` só conclui por ação explícita (`marco concluir <id>` no CLI).

Sem LLM, sem multiplayer, sem interface gráfica.
