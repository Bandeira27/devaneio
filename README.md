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

Comandos: `olhar`, `entrar <id> "<nome>" [FOR=3 ...] [+item ...]`, `ir <local>`, `testar <habilidade>
<dificuldade> [modificador]`, `atacar <arma> <alvo> [modificador]`, `ferir <alvo> <quantia>`,
`curar <alvo> <quantia>`, `descansar`, `ficha`, `marcos`, `marco ativar|concluir|falhar <id>`, `log`, `fim`, `ajuda`, `sair`. Com mais de um personagem, prefixe: `aria: testar lutar normal`.
O arquivo da partida é salvo após cada ação e é a fonte da verdade. `atacar` compõe no CLI
um `resolve_check` (habilidade da arma contra a dificuldade de ataque do sistema) e, em acerto, um `deal_damage`. A arma precisa estar no inventário; a arma padrão do sistema (`combat.default_weapon`) está sempre disponível.

A partida termina em **vitória** (todos os marcos concluídos) ou **derrota** (todo o grupo com hp 0). O desfecho é derivado do estado por `game_status`; o motor não se recusa a agir, e o CLI trava as ações exceto consulta. `descansar` recupera hp pela fórmula `rest.heal`, só sem hostis vivos no local, e gasta o turno.

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
- Etapa 7: narração por gramáticas. Pacote `pt-br` (`backend/src/devaneio/narration/data/pt-br.json`, contrato em `contract/narration.schema.json`) no estilo Tracery; `Narrator.narrate(evento, índice, estado)` gera prosa na exibição, sem gravar no estado e sem consumir `rng_draws`. O CLI mostra a prosa e, abaixo, a linha mecânica entre colchetes.
- Etapa 8: cura e descanso (`heal`, `rest`, com `rest.heal` no sistema de regras), `game_status` (vitória e derrota derivadas do estado, sem campo novo), inventário exigindo a arma em `atacar`, comandos `curar`, `descansar` e `entrar ... +item` no CLI.
- Etapa 9: LLM opcional (`devaneio.llm`). Interpreta texto livre do jogador em ações validadas pelo motor e narra os eventos em prosa, com a gramática como fallback.

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
| `heal` / `rest` | campanha (+ regras) | `heal` / `rest` |
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

## LLM (opcional)

O jogo funciona inteiro sem LLM. Quando configurado, ele faz dois papéis, e **só propõe**:

1. **Interpreta texto livre.** Uma linha que não começa por comando conhecido ("tento convencer
   o ferreiro", "vou até a floresta") vai ao modelo com o contexto da partida e um catálogo de
   ids. Ele responde um JSON com até 3 ações (`check`, `attack`, `move`, `rest`) e, opcionalmente,
   uma fala. Cada ação vira um comando do CLI e passa pelas mesmas funções e validações do
   motor. É tudo ou nada: se alguma falhar, nada é aplicado, o erro volta ao modelo como
   feedback e há uma segunda tentativa; depois disso o jogador vê o erro e o estado não muda. O
   modelo escolhe habilidade e dificuldade, mas nunca rola dados nem decide dano. Dano e cura de
   quantia arbitrária e mudanças diretas de marcos ficam de fora do que ele pode propor. Ids são
   slugs validados, então a proposta não consegue injetar outro comando.
2. **Narra.** Um parágrafo de prosa por ação, abaixo do qual saem as linhas mecânicas. A prosa
   é só exibição e nunca volta ao estado; se o modelo falhar ou responder fora do formato, o
   CLI cai na gramática e avisa.

Configuração, só por variáveis de ambiente (nada é gravado em partida, campanha ou repositório):

```bash
export DEVANEIO_LLM_BASE_URL=http://localhost:11434/v1   # qualquer servidor no formato OpenAI chat/completions
export DEVANEIO_LLM_MODEL=nome-do-modelo
export DEVANEIO_LLM_API_KEY=...                          # opcional (modelos locais costumam dispensar)
export DEVANEIO_LLM_TIMEOUT=60                           # opcional, em segundos
```

`jogar --sem-llm` ignora a configuração. **Privacidade:** com LLM ligado, o contexto da partida
(local, grupo, NPCs presentes com seus segredos, marcos ativos, eventos recentes) é enviado ao
servidor configurado, e o CLI avisa na abertura. A chave só viaja no cabeçalho da requisição. O
cliente usa só a biblioteca padrão; pede `response_format: json_object` e, se o servidor recusar
(HTTP 400/422), repete sem o campo e valida o JSON por conta própria.

## Narração

A narração é uma camada de exibição: o estado guarda só o texto mecânico de cada evento, e
`devaneio.narration.Narrator` transforma evento em prosa a partir de um **pacote de narração**
(JSON, estilo Tracery): regras com alternativas, expansão recursiva de `#simbolo#` e variáveis
do evento (`#ator#`, `#alvo#`, `#arma#`, ...). A regra é escolhida por tipo e variante
(`check.success`, `damage.golpe_queda`, `director.tenso`...); evento sem regra sai com o texto
mecânico. A variedade vem de um RNG próprio semeado por (semente da partida, índice do evento):
reproduzível, e sem tocar na aleatoriedade do jogo. Pacotes são validados na carga: toda
referência precisa ser regra ou variável do tipo de evento. Quando houver LLM, ele entra por
este mesmo contrato: evento entra, prosa sai.

Sem multiplayer, sem interface gráfica.
