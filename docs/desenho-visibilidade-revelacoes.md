# Desenho: visibilidade e revelações pelo motor

Primeiro passo do [rumo de extensibilidade](rumo-extensibilidade.md). Este documento fixa o vocabulário e o
modelo antes do código; a implementação segue a ordem dos commits no fim.

## Problema

- O único segredo é `Npc.secrets`: lista de textos soltos, sem id, sem condição e sem estado "revelado".
- `Fact` existe no `GameState`, mas nada o cria nem lê.
- O LLM da mesa recebe os segredos por uma chave global (`--segredos-no-llm`), tudo ou nada, e a regra "não
  revele" depende de o modelo obedecer.
- Só NPC tem campo privado. Local, facção e marco não têm.

## Vocabulário

- **Público**: o que qualquer jogador pode saber. Nome, descrição, saídas, o que o `olhar` mostra.
- **Privado**: notas do autor (`private_notes`) e fatos ainda não revelados. Só o anfitrião vê.
- **Fato** (`FactDef`): uma informação da campanha que começa privada e pode virar pública.
- **Revelado**: o fato já foi tornado público pelo motor ou pelo anfitrião. O estado guarda o turno.
- **Plateia**: quem recebe a informação. Anfitrião vê tudo. Jogadores e o LLM da mesa veem o público mais os
  fatos revelados. O LLM só recebe o privado se o anfitrião ligar `--segredos-no-llm` ou, no CLI solo, por padrão.

Regra de ouro: o que não é entregue ao modelo ele não pode repetir.

## Modelo de dados

Na campanha (estática):

- `FactDef(id, text, about, reveal_when)`. `about` aponta um NPC, local, facção ou marco e serve só de
  rótulo de exibição. `reveal_when` é uma lista de condições (todas precisam valer). **Vazia**: só o
  anfitrião revela, pelo comando `revelar`.
- `Campaign.facts: list[FactDef]`.
- `private_notes: list[str]` em `Location`, `Faction`, `Npc` e `Beat`. Nunca são reveladas.
- `Npc.secrets` deixa de existir: cada segredo vira um `FactDef`.

No estado (dinâmico):

- `GameState.revealed_facts: dict[Id, int]`, id do fato para o turno em que foi revelado.
- O `Fact` antigo some. O texto fica na campanha, o estado só guarda o que mudou.

Nova condição, na mesma união fechada das condições dos marcos:

- `CheckPassed(kind="check_passed", skill_id)`: vale se algum evento `check` daquela habilidade terminou em
  sucesso ou sucesso crítico. Combina com as outras por E, como toda lista de condições (por exemplo
  `at_location vila` mais `check_passed persuasao`). É "alguma vez": não exige que o teste tenha sido no local.

Validação (lista de erros, como o resto): ids de fato únicos, `about` existente e referências das condições
de `reveal_when` conferidas pela mesma função usada nos marcos.

## Motor

- `reveal_facts(state, campaign)`: puro. Para cada fato oculto com `reveal_when` não vazio e todas as condições
  valendo, marca como revelado e registra um `Event(kind="reveal")` com o texto e o id.
- `reveal_fact(state, campaign, fact_id)`: ação do anfitrião. Erro se o id não existe ou já foi revelado.
- O diretor chama `reveal_facts` em `direct()`, junto de `advance_beats`. A camada `game` também chama depois
  de cada comando, para um teste bem-sucedido revelar na hora e não só no fim do turno.
- O motor continua sem I/O e sem aleatoriedade própria.

## Visibilidade por plateia

- `build_context` troca `include_secrets` por `include_private`. Sempre vão os fatos revelados (`fatos`).
  Só com `include_private` vão os fatos ocultos e as notas privadas.
- `CampaignView` (jogador) mostra os fatos revelados. `PlayerStateView` mostra `revealed_facts`. Fatos ocultos
  e `private_notes` nunca saem do anfitrião.
- `olhar` lista "Você sabe:" com os revelados.
- Evento `reveal` ganha narração no pacote pt-br e conta como público: o texto do fato revelado é público
  por definição.

## Migração

- A campanha de exemplo passa os dois segredos para fatos: o caminho do ferreiro revelado por um teste
  bem-sucedido no local, a identidade do sacerdote quando ele cai.
- **Quebra de compatibilidade, assumida**: partidas salvas com `facts` no estado e campanhas com `secrets` no NPC
  deixam de carregar (o schema recusa campo desconhecido). Não há migração automática; o projeto ainda não tem
  conteúdo publicado. Quem tem campanha própria troca cada `secrets` por um item de `facts` com `about`.

## Limites conhecidos

- `check_passed` olha o log inteiro: não exige que o teste tenha sido no local nem contra um NPC. O exemplo do
  ferreiro (`at_location vila` mais `check_passed persuadir`) revela ao entrar na vila depois de persuadir
  qualquer um em outro lugar. Alvo e local no teste ficam para quando houver ações declarativas.
- `skill_id` de `check_passed` não é conferido contra o sistema de regras na carga: erro de digitação deixa o fato
  sem revelar, sem aviso. Cabe ao validador de autoria do passo 2.
- `about` é só rótulo e aparece a jogadores e ao LLM quando o fato é revelado. Apontar para um marco pendente ou
  para um NPC que o grupo não conhece entrega o título ou o nome. Combine a revelação com o que o grupo já viu.
- Para o LLM, fato oculto com `about` de facção nunca é enviado (só sem `about`, do local, de marco ativo ou de
  NPC presente).

## Fora desta etapa

Copiloto do anfitrião, editor, ações declarativas e verificação da saída do LLM contra segredos.

## Ordem dos commits

1. Este documento.
2. Schema (`FactDef`, `private_notes`, `revealed_facts`), validação e contrato regenerado.
3. Condição `check_passed`.
4. Motor de revelação, diretor, comando `revelar` e narração do evento.
5. Visibilidade: contexto do LLM, visões do jogador, `olhar`.
6. Campanha de exemplo e documentação.
