# Chat da mesa

**Status: decidido e implementado em 2026-11-20** (servidor, API e a folha "Conversa" na mesa). A regra 9 do [AGENTS.md](../AGENTS.md) não lista o chat como
fora de escopo, e o dono pediu a funcionalidade. O desenho segue o do [banco](desenho-banco.md) e do
[long-poll](api-http.md).

## O que é

Uma conversa **entre os jogadores da mesa**, só para a mesa toda. Não passa pelo motor nem pelo LLM: não vira
`Event`, não muda o `GameState`, o mestre de IA não lê nem responde. É o canto onde o grupo se combina ("vamos pelas
ruínas?") sem misturar com o que o personagem faz.

## Decisões (do dono, 2026-11-20)

- **Guardado no banco, por mesa.** Tabela `chat_messages` (migração 4). O histórico sobrevive a reinício, entra no
  backup e some junto com a mesa apagada de vez. Mesa arquivada guarda a conversa; restaurar a traz de volta.
- **Só mensagem para a mesa toda.** Sem sussurro nesta fatia: não há regra de visibilidade nova a errar.
- **Fases:** conversa na sala de espera, em jogo e pausada. Mesa encerrada é só leitura (`409 ended`).

## Modelo

`ChatMessage(table_id, seq, player_id, name, role, text, created_at)`, chave `(table_id, seq)`. `seq` sobe de 1 em 1
por mesa e continua depois de um reinício. `name` e `role` são o do jogador **na hora de enviar** (a mensagem não muda
se o nome mudar). O servidor guarda as últimas 500 mensagens por mesa; as mais antigas saem na gravação.

O texto tem 1 a 500 caracteres, limpo como uma linha de comando (`clean_line`): NFKC, sem caracteres de controle ou
invisíveis, o que também recusa quebra de linha. O servidor não escapa marcação; o front mostra tudo como texto.

## API

| Rota                              | Auth   | Resposta                                                                                         |
| --------------------------------- | ------ | ------------------------------------------------------------------------------------------------ |
| `POST /tables/{id}/chat` `{text}` | Bearer | `201 ChatMessageView`. `409 ended`, `429 chat_rate_limited` (1 mensagem por segundo por jogador) |
| `GET /tables/{id}/chat?since=N`   | Bearer | `ChatView {messages, chat_seq}`: até 100 mensagens com `seq` > `N`, as mais recentes, em ordem |

O acompanhamento ao vivo reaproveita o long-poll de `GET /tables/{id}/events`: `EventsView` ganha `chat` e
`chat_seq`, e a rota aceita `since_chat`. Como com `since_talk`, com `wait` e **sem** `since_chat` (parâmetro ausente) o histórico
não conta como novidade (só mensagens posteriores à chamada acordam a espera). Um `since_chat=0` **explícito** significa
"desde o começo" e conta: o app sempre o envia, para uma mensagem enviada entre duas chamadas de um chat ainda vazio
não se perder. Enviar uma mensagem acorda quem espera
(`announce_change`).

## Onde mora

Só o servidor: `server/chat.py`, com `ChatDesk` (a regra: autenticar, fase, intervalo, texto) e `ChatStore` (o banco). O
motor, o `game` e o LLM não sabem que o chat existe. O contrato ganha `ChatRequest`, `ChatMessageView` e `ChatView`.

## Interface

Uma folha "Conversa" aberta por um botão no cabeçalho da mesa (com contador de mensagens não lidas; o histórico que já
existia ao abrir a mesa não conta), com campo de uma linha e Enter para enviar. Nomes longos quebram, nunca estouram.
Um painel fixo ao lado do feed na tela larga fica para depois.

## Fora desta fatia

Sussurro para o anfitrião, edição ou exclusão de mensagem, moderação, "fulano está digitando", menções e anexos.
