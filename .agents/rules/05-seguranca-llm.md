# 05. Segurança e fronteira do LLM

O LLM é **entrada não confiável**. O que ele devolve é um palpite a validar, nunca uma ordem.

## Regras

1. **O LLM só propõe.** A proposta (`Proposal`, até 3 ações) tem allow-list: `check`, `attack`, `move`, `rest`.
   Dano e cura arbitrários e mudanças diretas de marcos ficam **fora**. Não ampliar a allow-list sem o dono.
2. **Toda proposta vira linha de comando** e passa por `execute()` (`game/commands/`), reaproveitando as validações do motor.
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
    configurado, e o CLI avisa na abertura. Não aumentar o contexto enviado sem atualizar esse aviso e `docs/llm.md`.
    Na mesa em grupo, o LLM é o do processo do servidor (ambiente de quem o roda) e `TableView.llm.notice` diz a
    todos os jogadores para onde o texto e o estado vão; a chave nunca entra em requisição, resposta ou arquivo. Na
    mesa os segredos dos NPCs **não** vão ao LLM por padrão (a fala dele chega a todos); `--segredos-no-llm` os envia e
    o aviso (`LlmView.secrets`) muda. No CLI solo continuam indo. O copiloto do anfitrião (item 22) recebe a
    campanha inteira de qualquer forma, e o aviso também diz isso.

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
16. **Convite e visão por papel**: no `POST .../players` e no `POST .../preview` (que só devolve o título da campanha a
    quem tem o convite), mesa inexistente e convite errado respondem igual (401). O limite de 8 jogadores só vale
    depois do convite, e a prévia nem o consulta. O `GET .../{id}` sem token ainda revela se a mesa existe: aceito,
    o id tem 64 bits. Quem não é anfitrião só vê o que o `olhar` do CLI mostra: `TableView.state` é
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
    os eventos. O comando `log` é do anfitrião; o jogador lê `GET .../events`. A narração compartilhada do LLM e o
    prompt de proposta (`hide_events`) só recebem eventos que os jogadores veem, porque a fala do modelo vai a todos.
    Campo novo em `Event.data` que cite NPC precisa entrar em `PARTICIPANT_KEYS` (um teste percorre eventos reais do
    motor e falha se um id de NPC aparecer sob outra chave). O motor grava em `data["npc_locations"]` onde estava
    cada NPC do evento, então o filtro não depende de o NPC continuar lá (evento antigo sem o campo usa o local
    atual); `npc_ids_at` é o critério único do `olhar` e das visões. Um
    marco que conclui por `npc_down` de NPC escondido revelaria a queda dele pelo título: autor de campanha não deve
    ativar esse marco com o grupo longe. O filtro custa cerca de 2 ms para 1.500 eventos.
    **O que o cliente vê de `data`**: só o `EventView.outcome`, derivado por `server/turns.outcome_of` (grau do teste
    ou ataque, `damage`/`incapacitated`, `heal`), nunca rolagem, total ou margem. Com `outcome`, `text_of` tira do
    `text` o desfecho do fim da linha (", sucesso", ", fora de combate"), que o selo já diz. Campo novo no
    `EventView` é decisão de segurança: o `data` continua fora. Os testes estão em `test_server_outcome.py`.
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
    stderr do operador, não ao jogador). Com `--segredos-no-llm` o LLM recebe os segredos dos NPCs presentes (o aviso diz) e
    a `fala` que ele devolve pode repeti-los a todos: risco que o anfitrião aceita ao ligar a flag.
    A fala e a prosa do LLM (`Proposal.say`, `clean_narration`) passam por `llm/text.clean_text` (sem controle,
    formatação, bidi nem invisíveis; qualquer espaço vira um espaço): chegam à tela de outros jogadores.
    O custo do LLM do anfitrião é limitado por um intervalo mínimo por jogador entre textos livres (`429`, 5 s por
    padrão, `--intervalo-say`; conta mesmo com proposta vazia ou falha do LLM, e não conta recusa da mesa antes do
    LLM) e por um `say` por vez por mesa. A narração fica em memória no primeiro evento visível do lote; a fala vai ao mural
    em memória (`EventsView.talk`, 50 por mesa) para todos, com ou sem evento novo, e acorda o long-poll. Riscos aceitos: um jogador pode segurar o único
    slot de `say` por até ~3 min (timeout × 2 tentativas + narração), e uma tentativa perdida por `409 stale_revision`
    também custa chamadas ao LLM.
20. **Limites conhecidos e aceitos (mesa entre amigos, LAN)**: um token errado custa uma carga da partida (os
    hashes vivem no arquivo); `ThreadingHTTPServer` não limita conexões simultâneas; `max_tables` é conferido
    sem lock global (duas criações simultâneas podem passar o teto em uma). Não há limite de tentativas no
    convite: por isso ele tem 96 bits (`token_urlsafe(12)`). Uma tentativa errada de convite custa uma carga da
    partida sob o lock da mesa, e vale para `POST .../players` e para `POST .../preview` (a prévia é um segundo canal
    de tentativas, com o mesmo custo e a mesma proteção; o app só a chama uma vez, ao abrir o link).

## Copiloto do anfitrião (`server/copilot.py`, `llm/copilot.py`)

22. **O copiloto é do anfitrião e só lê.** A rota exige `role == "host"` (403 para os outros) e o LLM configurado
    da mesa. O contexto enviado é a campanha inteira, segredos, fatos ocultos e `private_notes` inclusive, **mesmo
    sem `--segredos-no-llm`**: decisão do dono, porque a saída não vai aos jogadores; por isso `LLM_NOTICE` diz a
    todos que o copiloto existe e o que ele recebe (item 11). Nada do que ele devolve pode chegar a outro jogador:
    não passa por `Presentation` (mural, narração), não vira `Event`, não é gravado no arquivo da mesa nem em log, e
    a pergunta também não é registrada. Ele não altera estado nem propõe comandos (não usa `execute`, `Proposal` nem
    `authorize_proposal`). Uma chamada ao LLM por vez por mesa (vaga própria, `409 copilot_busy`) e intervalo mínimo
    (`429 copilot_rate_limited`, que conta mesmo se o LLM falhar); falha do LLM é `502` genérico com o detalhe só no
    stderr. O contexto tem teto (`MAX_CONTEXT_CHARS`): acima dele encolhe em etapas com um `aviso` ao modelo e, se ainda
    não cabe, `422 context_too_large` antes de chamar o LLM. A resposta passa por `clean_multiline` (sem controle, ANSI, bidi nem invisíveis; até 2000 caracteres)
    porque chega à tela do anfitrião. Qualquer saída do copiloto que passe a ir a jogadores quebra este item e
    exige trocar o contexto para o recorte público (`build_context` com `include_private=False`).

## Conteúdo do autor (`game/content.py`)

21. **Sistema de regras e pacote de narração do autor são dado não confiável.** O id vem da campanha e é um
    slug (sem `..`); o arquivo fica só em `sistemas/` ou `narracoes/` ao lado da campanha, o caminho resolvido
    precisa estar dentro dessa pasta (symlink para fora dela é recusado), o tamanho é limitado
    (`MAX_CONTENT_BYTES`, 256 KiB) aplicado à leitura (lê no máximo o teto mais um byte), e o JSON entra por modelo Pydantic estrito. Pacote de narração é recusado na carga se tiver ciclo entre regras
    ou se o pior caso de uma regra passar de `MAX_EXPANDED_CHARS` (2000), e o narrador conta as expansões
    (`MAX_EXPANSIONS`) e cai no texto mecânico se estourar: gramática do autor não pode travar a mesa. `extends` é de um
    nível só (sem cadeia, ciclo nem recursão) e é mesclagem de dados: nenhum código do arquivo roda. Todo erro (JSON
    aninhado demais inclusive) vira `GameError` em português que cita o nome do arquivo e onde está o problema, nunca
    o caminho absoluto nem os valores do arquivo; no servidor, partida ilegível
    continua virando 500 genérico (item 15). Mudar o limite, a pasta ou a profundidade do `extends` exige atualizar
    este item e o teste que o prova. O hash do conteúdo no `SaveFile` só avisa, nunca decide nada.

## Navegador e UI (`server/static.py`; o app em `frontend/app/` ainda será construído)

23. **Estáticos e cabeçalhos.** O servidor só serve arquivos com `--web DIR`, e a API sempre vem antes (rota de API
    desconhecida continua 404 JSON). O caminho é decodificado uma vez e confinado à pasta: sem `..`, `%2e%2e`, NUL,
    barra invertida, segmento oculto, diretório nem symlink para fora, e **o alvo de um symlink dentro da pasta
    passa pelos mesmos filtros** de oculto e de extensão que o nome pedido; MIME por lista fechada (sem `.map`); só `GET` e `HEAD`. Toda
    resposta estática leva CSP (`script-src 'self'`; `style-src` com `'unsafe-inline'` como risco aceito),
    `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY` e `nosniff`. Mudar a CSP exige atualizar `docs/desenho-ui.md`
    e o teste que a prova.
24. **O front trata todo texto como não confiável.** O servidor sanitiza caracteres de controle em nomes, falas e
    prosa, mas **não escapa marcação**: nome de jogador, fala do LLM, narração e texto de campanha são exibidos só por
    interpolação (nunca `innerHTML` nem `bypassSecurityTrust*`; o lint que os barra é pré-condição do app e entra com
    ele, antes de qualquer tela). O token do jogador fica no
    `localStorage` e só viaja em `Authorization`: nunca em URL (o código do convite vai no fragmento). É um risco
    aceito (XSS leria o token), reduzido por CSP e pelo lint. **Pré-condição do editor de campanhas:** validar o
    cabeçalho `Host` e responder só em localhost, contra DNS rebinding.

25. **O editor de campanhas escreve arquivo sem login, então a defesa é o lugar.** Só existe com `--editor`; o servidor
    **recusa subir** com `--editor` fora de loopback (`127.0.0.1`, `::1`, `localhost`). Com ele ligado, todo pedido
    confere `Host` (só `localhost`, `127.0.0.1` ou `[::1]`, com a porta do servidor: contra DNS rebinding) e, em
    `POST`/`PUT`, o `Origin` quando vier (precisa ser o próprio servidor: contra CSRF); senão `403`. Sem `--editor`,
    `/editor/*` é `404`. O id da campanha é o único dado que vira nome de arquivo: slug (`^[a-z0-9][a-z0-9_-]*$`), sempre
    `<pasta de campanhas>/<id>.json`, nunca caminho vindo da requisição; a escrita é atômica (arquivo temporário e
    `os.replace`) e só acontece sem erro de validação. **Campanha com mesa não é sobrescrita** (as mesas releem o arquivo):
    o editor cria ou copia. O corpo do editor tem teto próprio (512 KiB). Os testes estão em `test_server_editor*.py`.

## Checklist ao mexer em `llm/`, `game/`, `cli/` ou carga de arquivos

- O que o modelo pode fazer mudou? Atualize a allow-list *e* o teste que a prova.
- Há caminho novo de texto externo até o motor, o shell, um arquivo ou um log?
- Há segredo que possa aparecer em exceção, `repr` ou mensagem de erro?
- O teste usa o servidor falso, não rede real?
