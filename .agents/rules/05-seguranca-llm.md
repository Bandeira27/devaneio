# 05. Segurança e fronteira do LLM

O LLM é **entrada não confiável**. O que ele devolve é um palpite a validar, nunca uma ordem.

## Regras

1. **O LLM só propõe.** A proposta (`Proposal`, até 3 ações) tem allow-list: `check`, `attack`, `move`, `rest`.
   Dano e cura arbitrários e mudanças diretas de marcos ficam **fora**. Não ampliar a allow-list sem o dono.
2. **Toda proposta vira linha de comando** e passa por `execute()` (`game/commands.py`), reaproveitando as validações do motor.
   Tudo ou nada: se uma ação falha, nada é aplicado. O modelo nunca rola dados nem decide dano.
3. **Ids são slugs validados**, então uma proposta não consegue injetar outro comando nem escapar do formato.
   Qualquer texto do modelo que vire argumento passa por validação antes de montar a linha de comando.
4. **Saída do LLM é lenienete na leitura, estrita na aplicação**: modelos de proposta usam `extra="ignore"`;
   o que chega ao motor é validado de novo por modelos estritos.
5. **A prosa do LLM é só exibição** e nunca volta ao estado. Se o modelo falhar, cai na gramática e avisa.
6. **Nunca executar código vindo de dado**: sem `eval`, `exec`, `compile`, `pickle`, `yaml.load`, `subprocess`
   com entrada externa, import dinâmico por nome externo. Regras do jogo são dados interpretados.
7. **Todo JSON externo** (campanha, partida, regras, resposta do LLM) entra por modelo Pydantic.
8. **Segredos** (`DEVANEIO_LLM_API_KEY`) só por variável de ambiente; nunca em log, mensagem de erro, partida,
   campanha, fixture, commit ou saída do CLI. A chave só viaja no cabeçalho da requisição.
9. **Rede**: só `http(s)` com host, validado em `LlmConfig` antes de qualquer requisição. Chamadas
   `urllib` levam `# noqa: S310` com essa justificativa, e **só** lá. Timeout sempre definido.
10. **Caminhos de arquivo vindos de dado não são confiáveis.** `SaveFile.campaign_path` é relativo ao arquivo da
    partida. No CLI local, `load_game` o resolve sem restringir `..` (um arquivo adulterado pode apontar para
    outro JSON local, e a mensagem de validação pode citar trechos dele): risco baixo e aceito. Qualquer código
    que sirva partidas a terceiros passa `campaign_root=` e a campanha precisa ficar dentro dessa pasta.
    `save_game` escreve de forma atômica (temporário na mesma pasta + `os.replace`).
11. **Privacidade**: com LLM ligado, o contexto da partida (inclusive segredos de NPCs presentes) vai ao servidor
    configurado, e o CLI avisa na abertura. Não aumentar o contexto enviado sem atualizar esse aviso e o README.
    Na mesa em grupo, o LLM é o do processo do servidor (ambiente de quem o roda) e `TableView.llm.notice` diz a
    todos os jogadores para onde o texto e o estado vão; a chave nunca entra em requisição, resposta ou arquivo.

## Servidor da mesa (`server/`)

12. **Campanha só por id do catálogo** (`Catalog`, pasta configurada na subida); o id da mesa vindo da URL é
    validado pelo formato que o próprio servidor gera (`^[a-f0-9]{16}$`) e o caminho resolvido precisa ficar
    dentro da pasta de dados antes de qualquer `open`. `load_game` recebe `campaign_root=`.
13. **Tokens e convite**: `secrets.token_urlsafe` (32 e 12 bytes), só hash sha256 no arquivo, comparação com
    `hmac.compare_digest` percorrendo todos os jogadores; o token em claro é devolvido uma vez, na criação.
    `log_request` registra método, rota e status: nunca cabeçalho, corpo nem query string.
14. **HTTP na stdlib**: corpo até 64 KiB (`413` antes de ler), `Content-Length` obrigatório (`411`),
    `Transfer-Encoding` recusado, só `application/json` (`415`; é também a defesa contra CSRF nas rotas sem
    token), timeout de socket, `Cache-Control: no-store`, bind `127.0.0.1` por padrão com aviso em `0.0.0.0`.
15. **Só `CommandError` e `ApiFailure` têm mensagem exposta.** Partida ilegível (`GameError`, `ValidationError`,
    `OSError`) vira `500 {"code": "internal"}` com traceback só no stderr: a mensagem original cita caminhos e
    trechos do arquivo. Segredos de NPC em `GET .../campaign` só para o anfitrião. `LlmConfig.host` e
    `description` nunca trazem usuário e senha da URL.
16. **Convite e visão por papel**: no `POST .../players`, mesa inexistente e convite errado respondem igual (401) e o
    limite de 8 jogadores só vale depois do convite (o `GET .../{id}` sem token ainda revela se a mesa existe: aceito,
    o id tem 64 bits). Quem não é anfitrião só vê o que o `olhar` do CLI mostra: `TableView.state` é
    `PlayerStateView` (sem `rng_seed`/`rng_draws`, que tornam o próximo sorteio previsível, sem `events` com `data`,
    sem `facts`, NPCs só do local e só como `NpcView`) e `GET .../campaign` é `CampaignView`. Campo novo em
    `GameState` ou `Campaign` não chega ao jogador até entrar de propósito nas visões;
    `tests/test_server_models.py` falha se `GameState` ganhar campo sem essa decisão. Nomes de jogador passam por
    NFKC e recusam controle, invisíveis e separadores de linha (impersonação, ANSI, bidi).
17. **Comandos da mesa**: quem age é política do servidor (`server/policy.py`), nunca o motor: o servidor
    **sempre** injeta o prefixo `id:` do personagem do jogador antes de chamar `execute` (sem prefixo o motor age
    pelo único personagem da partida, de quem for), recusa prefixo de personagem alheio (403) e confere que a linha
    remontada diz o mesmo comando. Os conjuntos de papéis particionam `game.COMMANDS` (um teste falha se um comando
    novo ficar sem papel). `marcos` é do anfitrião (lista marcos pendentes). Linhas de comando passam por NFKC e
    recusam controle e invisíveis, porque nomes de personagem entre aspas chegam à tela dos outros. A proposta do
    LLM para um jogador (etapa 4) passa pela mesma política antes de `execute`. `atacar` de jogador comum contra NPC
    de outro local responde como alvo inexistente (senão o ataque revela nome e hp e fere quem o `olhar` não mostra).
    `entrar` limita argumentos (30) e o tamanho de cada um (40).
    **Log filtrado**: o jogador comum não vê eventos sobre NPC que o grupo não via quando eles aconteceram (o `text`
    cita nome e hp: `ferir sacerdote` do anfitrião). `server/turns.hidden_events` reproduz os `move` para saber onde o
    grupo estava em cada evento, então o que é escondido continua escondido depois que o grupo chega ao NPC e `since`
    nunca perde evento visível; `EventView.index` mantém o índice original (a lista tem buracos) e `revision` conta todos
    os eventos. O comando `log` é do anfitrião; o jogador lê `GET .../events`. A narração compartilhada do LLM e o prompt
    de proposta (`hide_events`) só recebem eventos que os jogadores veem, porque a fala do modelo vai a todos. Campo novo
    em `Event.data` que cite NPC precisa entrar em `PARTICIPANT_KEYS` (um teste percorre eventos reais do motor e falha
    se um id de NPC aparecer sob outra chave). Premissas: o local de um NPC (`npc_ids_at`, critério único do `olhar`,
    das visões e do filtro) é estático (se um dia mudar, a estabilidade do filtro precisa gravar o local no evento); e um
    marco que conclui por `npc_down` de NPC escondido revelaria a queda dele pelo título: autor de campanha não deve
    ativar esse marco com o grupo longe. O filtro custa cerca de 2 ms para 1.500 eventos.
    Mensagens do motor em 422 ainda confirmam ids de locais (`ir xyz`). O anfitrião pode gastar a ação de um
    jogador agindo por ele (`bia: testar ...`). Descrições de marco aparecem na prosa quando o marco começa:
    autor de campanha não deve pôr spoiler nelas.
18. **Long-poll**: `wait` é inteiro de 0 a 30 (`400` fora disso); a espera usa uma `Condition` sobre o lock da mesa
    (soltá-lo enquanto espera é o que deixa os comandos passarem), só uma gravação acorda quem espera, e cada mesa
    aceita no máximo `MAX_WAITERS` (16) esperas: acima disso responde de imediato. Autenticação e 404 valem antes de
    esperar, e a vaga é devolvida num `finally`. A versão da mesa é lida antes de carregar a visão, para uma gravação
    no meio não ser dormida. Risco aceito: um jogador autenticado pode ocupar as 16 vagas da própria mesa (os outros
    degradam para polling); o teto de threads é mesas × 16, e o servidor não limita conexões ociosas (sec-http-8).
19. **Texto livre na mesa (`POST .../say`)**: a chave existe só no ambiente do servidor e nunca sai em resposta,
    log ou arquivo; o texto do jogador nunca é registrado e passa pelas regras de caracteres da linha (NFKC, sem
    controle nem invisíveis). Cada linha que o LLM propõe passa por `authorize_proposal` (mesmo `authorize` do
    jogador, com a sessão já avançada pelas ações anteriores) **antes** do `execute`, como feedback ao modelo; só
    ações de jogo (`testar`, `atacar`, `ir`, e `descansar` para o anfitrião) existem como proposta. O ator é fixado
    pelo servidor (`run_freeform(actor=)`), nunca pelo prefixo do texto. A chamada ao LLM roda fora do lock da mesa,
    com uma chamada por vez por mesa, e a gravação confere que revisão e mesa não mudaram. A prosa do LLM é só
    exibição: fica em memória, nunca no arquivo. Falha do servidor de LLM vira 502 genérico (o detalhe vai ao
    stderr do operador, não ao jogador). Risco aceito: o LLM recebe os segredos dos NPCs presentes (o aviso diz) e a
    `fala` que ele devolve pode, em tese, repeti-los a quem enviou o texto.
    A fala e a prosa do LLM (`Proposal.say`, `clean_narration`) passam por `llm/text.clean_text` (sem controle,
    formatação, bidi nem invisíveis; qualquer espaço vira um espaço): chegam à tela de outros jogadores.
    O custo do LLM do anfitrião é limitado por um intervalo mínimo por jogador entre textos livres (`429`, 5 s por
    padrão, `--intervalo-say`; conta mesmo com proposta vazia ou falha do LLM, e não conta recusa da mesa antes do
    LLM) e por um `say` por vez por mesa. A fala e a narração são guardadas em memória e vão a todos no primeiro evento
    visível do lote; sem evento novo a fala volta só a quem enviou. Riscos aceitos: um jogador pode segurar o único
    slot de `say` por até ~3 min (timeout × 2 tentativas + narração), e uma tentativa perdida por `409 stale_revision`
    também custa chamadas ao LLM.
20. **Limites conhecidos e aceitos (mesa entre amigos, LAN)**: um token errado custa uma carga da partida (os
    hashes vivem no arquivo); `ThreadingHTTPServer` não limita conexões simultâneas; `max_tables` é conferido
    sem lock global (duas criações simultâneas podem passar o teto em uma). Não há limite de tentativas no
    convite: por isso ele tem 96 bits (`token_urlsafe(12)`). Uma tentativa errada de convite custa uma carga da
    partida sob o lock da mesa.

## Checklist ao mexer em `llm/`, `game/`, `cli/` ou carga de arquivos

- O que o modelo pode fazer mudou? Atualize a allow-list *e* o teste que a prova.
- Há caminho novo de texto externo até o motor, o shell, um arquivo ou um log?
- Há segredo que possa aparecer em exceção, `repr` ou mensagem de erro?
- O teste usa o servidor falso, não rede real?
