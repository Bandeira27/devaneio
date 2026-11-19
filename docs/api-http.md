# API HTTP da mesa

Referência da API que o servidor expõe para jogar em grupo. Para subir o servidor, veja o [README](../README.md); as decisões por trás da UI estão em [`desenho-ui.md`](desenho-ui.md).

| Rota                                                  | Auth               | Resposta                                                                                                                                                                                                                                                       |
| ----------------------------------------------------- | ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /campaigns`                                      | —                  | `[{id, title, premise}]` do catálogo (`--campanhas`)                                                                                                                                                                                                           |
| `POST /tables` `{campaign_id, host_name, seed?}`      | —                  | `201 {table_id, host_token, invite_code, table}`; o token só aparece aqui                                                                                                                                                                                      |
| `POST /tables/{id}/preview` `{invite_code}`           | —                  | `200 {title}`: só o nome da mesa (o título da campanha), para a tela de entrar mostrar para onde o convite leva; convite errado e mesa inexistente respondem igual (401), igual ao de entrar; não consulta o limite de jogadores                               |
| `POST /tables/{id}/players` `{invite_code, name}`     | —                  | `201 {player_id, token, table}`; convite errado e mesa inexistente respondem igual (401); até 8 jogadores, nomes únicos                                                                                                                                        |
| `POST /tables/{id}/commands` `{line, revision}`       | Bearer             | `CommandResult {revision, events, text, status, turn_ended}`; `line` é um comando do CLI (sem `id:` para o seu personagem)                                                                                                                                     |
| `POST /tables/{id}/say` `{text, revision}`            | Bearer             | texto livre: o LLM do anfitrião propõe ações e o servidor aplica; `SayResult` = `CommandResult` + `say` (fala do mestre, só para quem enviou) e `commands`. `409 llm_disabled` sem LLM                                                                         |
| `POST /tables/{id}/copilot` `{text}`                  | Bearer (anfitrião) | pergunta ao copiloto do anfitrião (ver abaixo); resposta `{text}` só para ele. `403` para jogador, `409 llm_disabled` sem LLM, `409 copilot_busy`, `429 copilot_rate_limited`                                                                                  |
| `GET /tables/{id}/events?since=N&since_talk=T&wait=S` | Bearer             | `EventsView {revision, events, talk, talk_seq}`: eventos de posição `N` em diante (cada um com `prose` da gramática, o `outcome` do selo e sem `data`) e falas com `seq` > `T`. Com `wait` (0 a 30 s) e nada novo, **espera** uma gravação da mesa (long-poll) |
| `POST /tables/{id}/lifecycle` `{action, revision}`    | Bearer (anfitrião) | muda a fase da mesa (`start`, `pause`, `resume`, `end`; ver "Fases") e devolve o `TableView` do anfitrião. `403` para jogador, `409 stale_revision`, `409 no_characters`, `409 invalid_transition`, `409 ended`                                                |
| `GET /tables/{id}`                                    | Bearer             | `TableView`: mesa, jogadores, `revision` (número de eventos), `status`, `phase`, `elapsed_seconds`, `llm`, `state`                                                                                                                                             |
| `GET /tables/{id}/rules`                              | Bearer             | `RulesView`: o catálogo do sistema de regras (atributos com limites, habilidades e armas com fórmula, dificuldades, modificadores, `combat`) para montar botões e o formulário de personagem                                                                   |
| `GET /tables/{id}/campaign`                           | Bearer             | anfitrião: a `Campaign` inteira; jogador: `CampaignView` (só o que o `olhar` mostra)                                                                                                                                                                           |

## Fases da mesa

A mesa nasce na **sala de espera** (`phase: "lobby"`): convidados entram (`POST /players`) e criam personagem (`entrar`),
mas a história não começou (nenhum evento, nenhum marco ativo; `revision` 0). O anfitrião **inicia** (`start`, exige ao
menos um personagem): a abertura da história roda e a fase passa a `running`. Ele também **pausa** e **retoma**
(`paused` ⇄ `running`) e **encerra** (`ended`, definitivo; também vale a partir da sala). Uma mesa gravada antes
dessas fases abre em `running`.

| Fase      | Jogador                                         | Anfitrião                                                   |
| --------- | ----------------------------------------------- | ----------------------------------------------------------- |
| `lobby`   | ler e criar personagem (`entrar`)               | o mesmo; `409 not_started` para o resto                     |
| `running` | tudo que já podia                               | tudo que já podia                                           |
| `paused`  | só ler (`409 paused` para o resto)              | tudo, inclusive texto livre (a pausa trava só os jogadores) |
| `ended`   | só ler (`409 ended`); entrar: `409 table_ended` | só ler                                                      |

Cada mudança vira um evento no log (`table_started`, `table_paused`, `table_resumed`, `table_ended`), então ela muda a
`revision` e acorda quem espera no long-poll. `elapsed_seconds` é quanto a partida **rodou** (a pausa não conta), no
relógio do servidor; o cliente faz o relógio andar sozinho enquanto a fase é `running`. `phase` é um eixo à parte do
`status` (`active|won|lost`), que é o desfecho da história.

Erros vêm como `{"error": {"code", "message"}}` (400 corpo inválido, 401 token, 404 mesa/campanha/rota,
409 limite de mesas, 411/413/415 corpo, 500 genérico). O contrato da API está em `contract/api_requests.schema.json`
(validation) e `contract/api_responses.schema.json` (serialization), de onde saem `frontend/src/contract/api_*.ts`.

Cada mesa é uma linha da tabela `tables` do banco do servidor (`<--dados>/devaneio.db`, ver [`desenho-banco.md`](desenho-banco.md)): o `GameState` e a mesa (jogadores com hash do token, hash do convite, quem já agiu no turno) como JSON, e a campanha pelo caminho relativo à pasta de campanhas. O anfitrião (mestre) vê o `GameState` e a `Campaign`
inteiros; um jogador comum vê só o que o `olhar` do CLI mostra: `PlayerStateView` (sem `rng_seed`/`rng_draws`, que tornariam
o próximo sorteio previsível, sem o log com `data`; com `revealed_facts`, só fatos já revelados; NPCs só os do local, só com vivo, hp e hostil; só os
marcos que já começaram) e `CampaignView` (título, premissa, local com saídas, NPCs ali, marcos e fatos revelados). `TableView.role` diz qual dos
dois ramos veio. Nomes de jogador são normalizados (NFKC) e recusam caracteres de controle ou invisíveis. O CLI segue com o arquivo de partida e não usa o banco; as partidas de mesa em JSON de antes do banco entram por `devaneio importar`
(idempotente, preserva id, tokens e convite, **não toca nos arquivos originais**, recusa com o motivo o que não serve; precisa do servidor parado, que é quem segura o banco). Ao subir, o servidor só olha a pasta de dados e avisa quantos `<id>.json` ainda entrariam e **lista os que o importador recusaria, com o motivo** (até 10; o resto vira "e mais N"), sem gravar nem mover nada. `--host 0.0.0.0` expõe HTTP em
claro, tokens inclusive: use rede local, VPN ou um proxy TLS (o servidor fecha a conexão ao recusar um corpo e não
limita conexões simultâneas: é uma mesa entre amigos, não um serviço público). Com o LLM configurado (tela de Configuração ou ambiente do servidor),
`table.llm.notice` avisa todos os jogadores de que o texto e o estado da partida vão a esse servidor.

## Servir o front (`--web`)

Com `--web DIR`, o servidor entrega o build do app (`DIR/index.html` e seus arquivos) pela mesma origem da API, sem CORS.
A API vem sempre antes; só o que nenhuma rota de API reconhece pode ser arquivo, e só por `GET` e `HEAD`. Os arquivos
ficam confinados à pasta (sem `..`, `%2e%2e`, NUL, barra invertida, segmento oculto, diretório nem symlink para fora),
o tipo sai de uma lista fechada de extensões (sem `.map`) e toda resposta estática leva CSP, `Referrer-Policy`,
`X-Frame-Options` e `nosniff`. Arquivos com hash no nome são `immutable`; o resto revalida. Sem a flag, a rota `/`
continua 404 JSON. Desenho em [`desenho-ui.md`](desenho-ui.md).

## Quem age e quando

| Comando                                                        | Quem                                                              | Gasta a ação do turno                      |
| -------------------------------------------------------------- | ----------------------------------------------------------------- | ------------------------------------------ |
| `olhar`, `ficha`, `ajuda`                                      | todos                                                             | não                                        |
| `entrar`                                                       | jogador (um personagem só) e anfitrião (quantos quiser)           | não                                        |
| `testar`, `atacar`, `ir`                                       | o dono do personagem; o anfitrião por qualquer um (`id: comando`) | sim                                        |
| `descansar`, `fim`, `ferir`, `curar`, `marco`, `marcos`, `log` | só o anfitrião                                                    | não (`descansar` e `fim` encerram o turno) |

Cada personagem faz **uma ação principal por turno**; quando todos os personagens de pé ligados a um jogador agiram, o
servidor encerra o turno na mesma requisição (`turn_ended: true`) e o diretor age. O anfitrião pode encerrar antes
com `fim`. Um jogador comum nunca age sem prefixo injetado pelo servidor, nem por personagem de outro. `marcos`
é do anfitrião porque lista os marcos pendentes. `atacar` aceita o personagem de outro jogador como alvo e `ir`
move o grupo todo e gasta a ação de quem mandou: como no motor, é decisão da mesa. Jogador comum só ataca NPC do local
atual (os outros respondem como alvo inexistente). O anfitrião, ao agir por um jogador, gasta a ação dele. O log que o
jogador lê (`GET .../events`) **não traz eventos sobre NPC que o grupo não via na hora** (o que o anfitrião faz com `ferir`
num NPC escondido): o `index` de cada evento é o original, então a lista pode ter buracos, e `revision` conta todos os
eventos (pode subir sem evento novo para o jogador). `EventView.outcome` é só o desfecho para o selo do feed, igual para todos: o grau de um teste (`critical_failure`, `failure`, `success`, `critical_success`), de um ataque (`critical_miss`, `miss`, `hit`, `critical_hit`), `damage` ou `incapacitated` num dano, `heal` numa cura; `null` nos demais eventos. O servidor o deriva do evento e nunca expõe com ele dado, margem nem total. Com `outcome`, o `text` vem sem o desfecho no fim (", sucesso", ", fora de combate"): o selo o diz. O comando `log` é do anfitrião. Linhas de comando têm até 500
caracteres e passam por NFKC; controle e invisíveis dão `400`, e `entrar` aceita até 30 argumentos de até 40 caracteres.

`revision` é o número de eventos que o cliente viu: comando que muda a partida com revisão velha recebe `409` (leia
de novo). Erros dos comandos: 400 linha vazia ou com caracteres de controle, 403 papel ou personagem alheio, 409 revisão
velha, já agiu, partida encerrada ou segundo personagem, 422 o motor recusou.

## Acompanhar a mesa (long-poll)

O cliente guarda o `revision` da última resposta e chama `GET /tables/{id}/events?since=<revision>&wait=25` em
laço: a resposta volta assim que alguém grava um comando (ou vazia, com o mesmo `revision`, ao fim do prazo). Só
gravação acorda quem espera: comando recusado ou de consulta não acorda ninguém. Cada mesa aceita até 16 esperas
simultâneas; acima disso a resposta é imediata (o cliente deve esperar um pouco antes de tentar de novo). Uma espera
ocupa uma thread do servidor por até 30 s.

## Copiloto do anfitrião

`POST /tables/{id}/copilot` `{"text": "..."}` (até 500 caracteres) é uma pergunta avulsa ao LLM, **só do anfitrião**.
O copiloto recebe a **campanha inteira**, segredos, fatos ocultos, marcos pendentes com as condições, facções e
`private_notes` inclusive (o anfitrião já vê tudo pela API), e **não altera nada**: responde, sugere o próximo marco,
rascunha falas de NPC e avisa de spoiler. Quem aplica é o anfitrião, pelos comandos de sempre. A resposta volta só a
quem perguntou: não entra no mural nem na narração, não vira evento e não é gravada; a pergunta também não. O envio
do privado ao LLM vale **mesmo sem `--segredos-no-llm`** (o anfitrião configurou o LLM), e por isso `TableView.llm.notice`
diz a todos que o copiloto existe. Vaga e intervalo próprios, independentes do `/say`: uma consulta por vez por mesa
(`409 copilot_busy`) e 5 s entre consultas (`429`, `--intervalo-copiloto`; conta mesmo se o LLM falhar). O contexto tem teto (60 mil caracteres): se a campanha passa dele, encolhe em etapas (menos eventos, textos
cortados) com um aviso ao modelo, e se ainda não cabe responde `422 context_too_large`. Não há
memória entre perguntas. Desenho em [`desenho-copiloto.md`](desenho-copiloto.md).

## Texto livre pelo LLM na mesa

Com o LLM configurado **no servidor** (tela de Configuração ou `DEVANEIO_LLM_*`; a chave nunca vai em requisição de jogo, resposta ou arquivo de partida), `POST /tables/{id}/say`
manda o texto de um jogador ao LLM, que **só propõe** (as mesmas quatro ações do CLI: `check`, `attack`, `move`,
`rest`). Cada ação proposta passa pela mesma política do jogador que falou: um `rest` proposto para um jogador comum
é recusado e volta ao modelo como feedback (duas tentativas, tudo ou nada), e um ataque a NPC que o jogador não vê
responde como alvo inexistente. A proposta inteira, de até 3 ações, gasta **uma** ação principal do personagem; sem
ações (só conversa) nada é gravado e a ação não é gasta.

- **Privacidade:** `TableView.llm.notice` diz a todos para onde vão o texto e o estado da partida. **Por padrão só o público vai ao LLM da mesa** (fatos já revelados inclusive; fatos ocultos e `private_notes`
  ficam de fora), porque a fala dele chega a todos os jogadores e ele não pode repetir o
  que não recebeu; `--segredos-no-llm` envia também o privado (o aviso e `LlmView.secrets` passam a dizer isso), para o mestre de IA
  jogar com o que cada NPC esconde. No CLI solo, o jogador é o mestre e os segredos continuam indo. O servidor nunca
  registra o texto do jogador.
- **A chamada ao LLM roda fora do lock da mesa** (pode levar minutos): os comandos seguem passando, e a gravação só
  acontece se a mesa não mudou nesse intervalo (senão `409 stale_revision`, e a tentativa se perde). Só uma chamada
  de texto livre por vez por mesa (`409 say_busy`) e um **intervalo mínimo por jogador** entre dois textos livres
  (`429 say_rate_limited`; 5 s por padrão, `--intervalo-say` muda), porque cada um custa chamadas ao LLM de quem roda o
  servidor. O intervalo conta mesmo se a proposta vier vazia ou o LLM falhar; recusa da mesa antes do LLM não conta.
- **Narração:** o LLM escreve um parágrafo para o lote de eventos, guardado **só em memória** (os últimos 200 por
  mesa): vem em `EventView.narration` no primeiro evento do lote que os jogadores veem (nos outros é `null`), igual
  para todos, e some ao reiniciar o servidor. `EventView.prose` é sempre a narração da gramática do próprio evento,
  então o cliente mostra `narration` quando houver e `prose` no resto. Se o LLM falhar, `narration` fica `null`.
- **Fala (mural):** a fala do mestre ou do NPC não é evento (o LLM nunca escreve no estado): fica num mural em memória
  (as últimas 50 por mesa), com ou sem evento novo, e todos a leem em `EventsView.talk` (`seq`, `after` = revisão na
  hora, `to` = personagem que a provocou). O cliente guarda `talk_seq` e o devolve em `since_talk`; uma fala nova
  também acorda o long-poll. Os números vêm do relógio de parede e continuam subindo depois de reiniciar o servidor.
  Com `wait` e **sem** `since_talk` o mural antigo não conta como novidade (só falas posteriores à chamada acordam a
  espera): um cliente que não devolve `talk_seq` espera em vez de girar; para o histórico, chame com `wait=0`.
- **Autoria de campanha:** `description` de NPC, de local e de marco vai ao LLM e pode chegar a todos pela fala; o que
  ninguém pode saber vai em `facts` (revelado pelo motor, ver abaixo) ou em `private_notes` (nunca revelado); nenhum dos
  dois sai do servidor por padrão. Não ative um marco que conclui por
  `npc_down` de um NPC que o grupo não vê: o título do marco concluído revela a queda dele. O mesmo vale para um fato
  revelado por `npc_down`: combine com `at_location` (o exemplo faz isso), senão o evento `reveal` entrega o nome; e `about` aparece a todos quando o fato é revelado.
  Campanhas e partidas anteriores a `facts` não carregam: troque `secrets` por `facts` (ver o documento de desenho).
- A fala e a narração do LLM passam por um filtro (sem controle, ANSI, bidi nem invisíveis) porque chegam à tela dos
  outros. Falha do servidor de LLM é `502 llm_unavailable` sem detalhes do provedor (ficam no stderr).

## Configuração do LLM (`/editor/settings/llm`, só da máquina do servidor)

Mesma guarda do editor (`/editor/*`: loopback, sem cabeçalho de proxy, `Host` local e `Origin` do próprio servidor; senão 404 ou 403).

| Rota | Faz |
|---|---|
| `GET /editor/settings/llm` | `LlmSettingsView`: `source` (`screen`, `environment` ou `none`), `disabled` (`--sem-llm`), `base_url`, `model`, `timeout` guardados, `key_set` e `description`. **Nunca** traz a chave, nem parte dela. |
| `PUT /editor/settings/llm` | `LlmSettingsUpdate`: `base_url`, `model`, `timeout` e `api_key` opcional (ausente mantém a atual). Endereço só `http`/`https`, sem usuário e senha, parâmetros nem âncora; chave em ASCII visível, sem espaços. Mudar de servidor sem escrever a chave de novo é recusado. `422 invalid_settings` se recusar. Vale na hora. |
| `DELETE /editor/settings/llm` | apaga o que a tela guardou, chave inclusive: volta ao ambiente, se houver. |
| `DELETE /editor/settings/llm/key` | apaga só a chave. |
| `POST /editor/settings/llm/test` | uma chamada curta ao LLM em uso; `LlmTestResult` com `ok` e uma **frase fixa** (nunca o corpo do servidor nem o endereço). |

## Mesas arquivadas (`/editor/*`, só da máquina do servidor)

`DELETE /editor/tables/{id}` **arquiva** a mesa (não a apaga): ela sai do jogo (404 para quem a usava), da lista e do limite de mesas, e o estado e o
log ficam. `GET /editor/campaigns/{id}/archived-tables` lista as arquivadas; `POST /editor/archived-tables/{id}/restore` as traz de volta com os mesmos tokens
e convite; `GET /editor/archived-tables/{id}/log` devolve o log inteiro (só texto); `DELETE /editor/archived-tables/{id}` apaga de vez uma arquivada. Ver
[`desenho-editor.md`](desenho-editor.md).

`503 busy` (com `Retry-After: 1`) vale para qualquer rota se o banco seguir ocupado depois da espera e das novas tentativas.

