# Rumo: o Devaneio como plataforma de campanhas extensível

**Status: direção definida em 2026-11-15; os passos 1 a 3 estão implementados.** Este documento registra o que o dono
decidiu e o que ficou por detalhar. A regra 9 do [AGENTS.md](../AGENTS.md) liberou a UI da mesa (desenho em
[`desenho-ui.md`](desenho-ui.md)); o que depende de abri-la de novo (o editor de campanhas) está marcado. Os princípios do produto continuam no [README](../README.md).

## A ideia

O Devaneio deixa de ser um jogo com conteúdo embutido e passa a ser uma **plataforma de campanhas**: um
conjunto pequeno de **ações primitivas** do motor e conteúdo livre do usuário por cima. O projeto já é assim
em parte; esta direção formaliza a fronteira e fecha as lacunas.

- O foco é **extensibilidade**. Gestão de campanhas (biblioteca, várias sessões por campanha, histórico,
  arquivar partidas) é possibilidade futura, fora do escopo.
- O autor típico **não é técnico**, mas técnicos também precisam de acesso. Os dois públicos valem para o
  editor e para o modelo extensível.
- **Dois modos, um formato:** arquivos JSON (com o JSON Schema de `contract/` publicado, para editores de texto
  validarem e completarem) e um editor com formulários gerados do mesmo schema. Nada de dois produtos.

## Vocabulário (a detalhar)

| Termo | O que é | Onde vive hoje |
|---|---|---|
| **Primitiva** | verbo do motor: teste, dano, cura, mover, descansar, marcos, fim de turno | `backend/src/devaneio/engine/`, código |
| **Sistema** | regras como dado: atributos, habilidades, armas, fórmulas, dificuldades, graus, combate, descanso | `rules/data/default.json` |
| **Conteúdo** | campanha (locais, NPCs, facções, marcos, condições) e pacote de narração | `campaigns/*.json`, `narration/data/pt-br.json` |

## Decisões

1. **Regras são dados, nunca código** (decisão fixa, mantida). A extensão é uma **linguagem própria nossa,
   declarativa**: uma ação definida pelo usuário é uma sequência das primitivas existentes (teste, dano, cura,
   mover, ativar marco...), interpretada pelo motor. Sem script livre e sem sandbox de código. Se um dia faltar
   poder, a saída são extensões escritas e revisadas pelo projeto, nunca enviadas pelo usuário. Reabrir "regras
   são dados" é decisão do dono.
2. **Tudo parametrizado, com padrão e coerência.** Cada número tem valor padrão no sistema base, e o sistema do
   usuário passa por verificação de coerência (como `validate_rules` já faz). Um sistema novo nasce como cópia
   ou `extends` do "Devaneio Básico", sobrescrevendo só o que mudou.
3. **Sistemas e narrações do usuário carregam de arquivo.** Implementado: pastas `sistemas/` e `narracoes/` ao lado
   da campanha, com `extends` de um nível e o comando `verificar` (ver o documento de desenho do passo 2).
4. **Conteúdo empacotado com id e versão.** Parcial: a partida guarda o hash do sistema e da narração e avisa
   quando mudam; versionar o conteúdo com migração segue em aberto.
5. **A classificação de cada ação vira metadado**, não conjuntos fixos no servidor: se é leitura, ação
   principal ou do anfitrião, quais campos de evento citam NPC (para o filtro do log), e se o LLM pode propô-la.
   Hoje isso está em `server/policy.py`, em `PARTICIPANT_KEYS` e na allow-list de `llm/actions.py`.

## O LLM nesse rumo

O risco a reduzir: o modelo repetir a quem não deve o que recebeu. Nada elimina isso a não ser **não entregar
a informação**. Em ordem de valor:

1. **Público e privado por campo.** Todo elemento tem campo público e notas privadas (generaliza `secrets`).
   Por padrão o LLM só recebe o público. O editor mostra uma **prévia do que o modelo vai ver**.
2. **O motor decide as revelações.** Um segredo vira um `Fact` com condição de revelação (um teste bem-sucedido,
   por exemplo). O motor o marca como revelado e só então ele entra no contexto de todos. Implementado: `Campaign.facts` com `reveal_when` e `GameState.revealed_facts`.
   A regra "não revele" continua no prompt, mas deixou de ser a defesa principal.
3. **Uma geração por plateia.** Jogadores recebem saída gerada só com contexto público.
4. **Verificação da saída** contra segredos ainda não revelados, como defesa em profundidade (heurística).
5. **Fala restrita** a falas escritas pelo autor: seguro, mas perde naturalidade.

### Copiloto do anfitrião

Um assistente separado, só do anfitrião, com o contexto **privado** completo. Implementado (ver
[`desenho-copiloto.md`](desenho-copiloto.md)): `POST /tables/{id}/copilot`, pergunta avulsa, sem estado.

- **Não altera estado.** Responde, sugere o próximo marco, rascunha falas de NPC e avisa de risco de spoiler.
  Quem aplica é o anfitrião, pelos comandos de sempre ("o LLM só propõe").
- Sua saída vai por um canal só do anfitrião e **nunca entra no mural de falas**.
- Como o anfitrião configurou o LLM, o envio do contexto privado é aceitável; a mesa continua avisada de que o
  LLM existe.
- Custa chamadas extras: vaga e intervalo próprios, no mesmo espírito do `/say`.

## Ordem sugerida

1. Visibilidade (público e privado) e revelações decididas pelo motor.
2. Carregar sistemas e narração do usuário de arquivo, com `extends` e um **validador de autoria em português**
   (o aviso do marco por `npc_down` de NPC fora de vista seria uma regra dele).
3. Copiloto do anfitrião (precisa do passo 1).
4. Ações declarativas, com a classificação como metadado.
5. Editor com formulários gerados do schema. Um mínimo, só de campanha, já depois do passo 2, para ter retorno
   cedo. **Segue fora de escopo na regra 9 do AGENTS.md** (a UI da mesa já foi liberada: ela vem antes do editor, e o
   editor só existirá com `--editor` e em localhost, ver [`desenho-ui.md`](desenho-ui.md)).

Antes de qualquer implementação, um documento de desenho detalhando o vocabulário acima.

## O que hoje é fechado no código

Referência para quem for mexer: o que o usuário **não** estende ainda.

- Os verbos do motor e o conjunto de comandos (`game/commands.py`, `COMMANDS`).
- Os tipos de condição dos marcos: uma união fechada de quatro (`schema/campaign.py`).
- O diretor: quem reage e os pesos da tensão (`engine/director.py`).
- Marcos sem efeitos, hp como único recurso (sem mana, estresse nem condições temporárias).
- As quatro ações que o LLM pode propor (`llm/actions.py`).
- Na mesa: a política por papel (`server/policy.py`) e as chaves de evento que citam NPC (`server/turns.py`).

## Pontos a pensar

- **Autor leigo:** mensagens de erro claras, duplicar e editar em vez de criar do zero, importar e exportar
  pacotes.
- **Texto livre de campanha** (`description`) vai ao LLM e pode chegar a todos pela fala: quanto mais livre o
  conteúdo, mais pesa. A orientação de autoria está no README.
- **Partidas salvas** referenciam a campanha por caminho: mudar o conteúdo exige uma política de versão.
