# Desenho: copiloto do anfitrião

Terceiro passo do [rumo de extensibilidade](rumo-extensibilidade.md). O copiloto é um assistente de LLM só do
anfitrião, com o contexto **privado completo**. Ele não altera estado: responde, sugere o próximo marco, rascunha
falas de NPC e avisa de risco de spoiler. Quem aplica é o anfitrião, pelos comandos de sempre ("o LLM só propõe").

## Decisões

- **Só na mesa HTTP.** Sem comando no CLI e sem UI (o frontend ainda não tem cliente).
- **Pergunta avulsa, sem estado.** Cada chamada leva o contexto atual e a pergunta. O servidor não guarda nada.
- **Contexto: a campanha inteira.** O anfitrião já vê tudo pela API, e só assim o copiloto sugere o próximo marco.
- **Custo próprio.** Vaga e intervalo mínimo independentes do `/say`: o copiloto não segura os jogadores nem o contrário.

## Rota

`POST /tables/{id}/copilot`, corpo `{"text": "..."}` (mesmo limite do `/say`: 500 caracteres, NFKC, sem controle),
resposta `{"text": "..."}` síncrona, `200`, `Cache-Control: no-store`.

- Só o anfitrião (outro papel: `403`). Mesa sem LLM: `llm_disabled`, como no `/say`.
- `409 copilot_busy` se já há uma consulta em andamento na mesa. `429 copilot_rate_limited` dentro do intervalo
  (5 s por padrão, `--intervalo-copiloto`); o pedido conta mesmo se o LLM falhar.
- Falha do servidor de LLM: `502 llm_unavailable` sem detalhe do provedor (o detalhe vai ao stderr).
- Não é comando do jogo: não entra em `COMMANDS` nem na política de papéis.

O intervalo e a vaga usam o mesmo portão do `/say` (`server/llm_gate.py`): recusar se o intervalo não passou
(`429`), recusar se já há uma chamada do mesmo tipo (`409`) e contar o pedido. Cada tipo tem a sua vaga no
`Storage` (`enter_slot`, `leave_slot`, `slot_cooldown_left`, `mark_slot`), então um não segura o outro.

## Canal e privacidade

A resposta volta só a quem perguntou. Ela **não** entra no mural nem na narração (`Presentation`), não vira
`Event`, não é gravada no arquivo da mesa nem em log; a pergunta também não é registrada. O anfitrião configurou o
LLM, então enviar o privado a ele é aceitável **mesmo sem `--segredos-no-llm`**. Por isso o aviso da mesa passa a
dizer a todos que o copiloto existe, que recebe a campanha inteira, segredos inclusive, e que a resposta dele não
volta aos jogadores.

## Contexto enviado

Sem ator e sem catálogo de ações, em JSON compacto: turno, local atual, grupo, todos os locais (descrição, saídas,
`private_notes`), facções, todos os NPCs (local, vivo, hp, disposição, descrição, `private_notes`), todos os marcos
(status, requisitos, condições, `private_notes`), todos os fatos (texto, sobre quem, revelado e quando,
`reveal_when`) e os últimos 15 eventos, sem filtro. Sem `rng_seed` nem `rng_draws`.

O prompt de sistema diz: você assessora o anfitrião e vê tudo, inclusive segredos; não altera nada nem afirma ter
aplicado algo; não inventa fato fora do contexto; responde curto. Uma chamada só, sem as duas tentativas do
proposer (custo). A resposta passa por `clean_multiline`: mantém quebras de linha, remove controle, ANSI, bidi e
invisíveis, e corta em 2000 caracteres, porque chega à tela do anfitrião.

## Limites conhecidos

- O contexto tem teto (`MAX_CONTEXT_CHARS`, 60 mil caracteres, cerca de 15 mil tokens). Passando dele, encolhe em
  etapas: 5 eventos recentes, nenhum evento, textos livres cortados em 200 caracteres; o próprio contexto ganha um
  `aviso` para o modelo não tratar o que falta como inexistente. Se mesmo assim não cabe, `422 context_too_large`
  sem chamar o LLM (o pedido conta no intervalo).
- Sem memória entre perguntas. Quem quiser continuidade cola o que importa na pergunta.
- O copiloto não executa nada: sugerir um comando não o aplica.

## Ordem dos commits

1. Este documento.
2. Contexto, prompt e `ask_copilot` (`llm/copilot.py`) e `clean_multiline`.
3. Mesa de consulta no servidor, vaga e intervalo, rota, modelos de API, contrato e aviso.
4. README, regra 05 e rumo.
