# O banco do servidor

**Status: aprovado em 2026-11-19; as fatias 1 (base do banco e configuração do LLM) e 2 (mesas, partidas e tokens no banco)
estão implementadas. A 3 (exportar, backup e histórico) segue em aberto.**

O servidor guarda o que a aplicação gera e muda em **SQLite**, pelo **SQLAlchemy 2.0**. O que o autor escreve
(campanhas, sistemas de regras, narrações) continua **JSON em arquivo**, e o CLI continua com o arquivo de partida.

## Decisões

- **SQLite** pela biblioteca padrão por baixo; **SQLAlchemy 2.0** como ORM (dependência de runtime nova, regra 5 do
  `AGENTS.md`). Justificativa: mapeamento tipado (`Mapped[...]`, mypy estrito), transações e pool de conexões entre as
  threads do `http.server` resolvidos pela biblioteca, o esquema declarado num lugar só e consultas que sobrevivem a uma
  troca de SGBD. O SQL continua por baixo: o ORM o gera.
- **Modelos do ORM são separados dos Pydantic do contrato**: o ORM guarda, o Pydantic valida; a conversão fica na borda
  do armazenamento, em `server/`. Nada de SQLModel.
- **Só o servidor conhece o banco**: um contrato do import-linter proíbe `sqlalchemy` e `sqlite3` em `game`, `engine`,
  `narration`, `llm`, `rules`, `schema`, `rng` e `cli`. O motor segue puro; o CLI segue em arquivo.
- **Estado da partida é JSON** numa coluna. Os eventos continuam **dentro** de `state.events`, a única fonte: nenhuma
  tabela `events` (duas fontes divergiriam). Reabrir só com medida: o JSON da partida passar de ~1 MB, a gravação inteira
  virar gargalo ou surgir consulta entre mesas. Nesse caso a tabela seria a única fonte (`(table_id, idx)`), o estado
  gravaria `events=[]` e o adaptador montaria o `GameState` juntando as linhas em ordem.
- **A chave do LLM não mora no banco.** Fica em `<dados>/llm.key` (`0600`), para cópia, backup e exportação do banco
  não levarem credencial. Endereço, modelo e tempo ficam na tabela `settings`.

## Premissa: um banco, um processo

O SQLite é usado por **uma única instância do servidor**; o arquivo não é compartilhado entre processos nem servidores.
Imposto por um `flock` não bloqueante em `<dados>/devaneio.lock` (Unix; no Windows fica só documentado). O CLI não usa o
banco, então rodá-lo ao lado não conflita.

## Concorrência

O `http.server` cria uma thread por pedido; o **lock por mesa em memória continua** (serializa ler-alterar-gravar da mesma
mesa, e a espera de long-poll segue na `Condition` em memória, sem conexão). O SQLite tem **um escritor por vez no arquivo
inteiro**: mesas diferentes não se bloqueiam no Python, mas se enfileiram no banco. O WAL deixa leitores e um escritor
andarem juntos; **não** cria vários escritores.

- Cada operação abre a **sua** `Session` (`Database.read` / `Database.write`), nunca guardada nem passada a outra thread.
- Escrita começa com `BEGIN IMMEDIATE`; com `BEGIN` adiado, ler e depois escrever com outro escritor no meio dá `SQLITE_BUSY`
  na hora, sem esperar o `busy_timeout`.
- `busy_timeout` de 5 s; `BUSY`/`LOCKED` tem até 3 novas tentativas (50, 100 e 200 ms) e vira `503 busy` com `Retry-After`.
  A unidade de trabalho só mexe no banco, sem rede nem LLM, e pode rodar de novo.
- Ordem fixa: primeiro o lock da mesa, depois a transação, nunca o inverso. A transação nunca abrange chamada ao LLM.
- `synchronous=NORMAL` com WAL: uma queda do sistema pode perder a última transação, nunca corrompe. Aceito para um jogo.
- Pool de 5 conexões (mais 10 de reserva), `pool_timeout` de 10 s: estourar vira `503`, não trava a thread.

## Segurança do arquivo

- Pasta de dados `0700` e banco `0600`, criados assim desde o primeiro instante; `-wal` e `-shm` herdam o modo do arquivo
  principal e a pasta fechada cobre o resto. Pasta ou arquivo nosso e aberto: fechado na subida, com aviso. De outro
  usuário: o servidor recusa subir.
- Banco de versão mais nova que o código, ou arquivo com tabelas que não são do Devaneio: recusa. Sem `llm.key` em
  banco restaurado: LLM desligado até configurar de novo.
- Windows: modos POSIX não valem; a proteção é a do perfil do usuário.
- **Se as permissões do sistema não bastarem** (máquina compartilhada, pasta de backup aberta, hospedagem): usar só a
  variável de ambiente ou um gerenciador de segredos externo. Alternativas rejeitadas por ora: chaveiro do SO (dependência
  `keyring`) e cifra com senha (pede a senha a cada subida). Reabrir a conta se o servidor for hospedado ou multiusuário.

## A chave e o endereço

- A chave só é enviada ao servidor para o qual foi guardada: **mudar o endereço para outro servidor** (esquema, nome ou
  porta) sem escrever a chave de novo é recusado (`422`); o dono escreve a chave outra vez ou a apaga antes. Mudar só o caminho
  ou o modelo mantém a chave.
- O cliente de LLM **não segue redirecionamento**: o `Authorization` iria junto para um destino que o dono não escolheu. Um 3xx
  vira erro comum ("HTTP 302").
- A chave é ASCII visível, sem espaços (vai num cabeçalho HTTP).
- **SSRF por desenho:** o "testar conexão" e o endereço guardado aceitam qualquer `http`/`https`, inclusive `localhost` e a
  rede interna (o Ollama local precisa disso). Só o dono, em `localhost`, aciona a rota, e a resposta é uma frase fixa; resta
  que "recusou", "não conectou" e "tempo esgotado" funcionam como um oráculo de varredura de portas para quem já controla a
  máquina. Risco aceito.
- `settings_store.save` grava o **banco primeiro e a chave depois**, e descarta o cache em `finally`: o erro esperado é o do banco
  (ocupado), e ele nunca deixa a chave trocada sem a URL.

## Migrações

`PRAGMA user_version` e uma lista numerada em `server/migrations.py` (o módulo do dialeto: `PRAGMA user_version` e `sqlite_master` vivem ali de propósito). Cada migração é SQL explícito (não `create_all`) e
roda **inteira numa transação `BEGIN IMMEDIATE`, junto com o novo `user_version`**: uma falha desfaz o DDL e a versão
juntos. Só roda o que a versão atual ainda não tem. Antes de migrar um banco com dados sai uma cópia consistente
`devaneio.db.pre-vN.bak` (`0600`). Um teste migra do zero e confere o resultado contra os modelos do ORM.

**Quando adotar Alembic:** cerca de dez migrações ou mais; migração de dados em várias etapas ou necessidade de reverter
(downgrade); autogerar diferenças passar a compensar; mais de um ambiente de implantação; ou troca de SGBD (DDL e transação
mudam). Antes disso é uma dependência a mais sem ganho.

## Portabilidade

O SQLAlchemy facilita trocar de SGBD, mas **não garante** portabilidade: `BEGIN IMMEDIATE`, WAL, `PRAGMA`, o tratamento
de `BUSY` e o `flock` são do SQLite e ficam em `server/database.py`. Tipos genéricos e JSON como texto nos modelos. Sem
preparar Postgres antecipadamente.

## O que mudou onde (fatia 1)

`server/database.py` (arquivo, conexões, transações), `server/migrations.py`, `server/orm.py`, `server/settings_store.py`
(configuração do LLM), `server/models/settings.py` e as rotas `/editor/settings/llm` ([`api-http.md`](api-http.md)); o
`TableService` consulta o LLM em uso a cada pedido, e `SayDesk` e `CopilotDesk` sempre existem.

## Mesas no banco (fatia 2)

A tabela `tables` guarda uma mesa por linha: `id`, `campaign_path` (relativo à pasta de campanhas, com índice), `state`
(o `GameState`, com os eventos dentro), `meta` (a `TableMeta`: jogadores, hashes de token e de convite, fase, tempo),
`content` (as impressões digitais de regras e narração, opcional), `created_at` e `updated_at`.

- **Sem tabela `players`.** O plano previa uma, para autenticar por hash sem carregar a partida; mas os jogadores já estão na
  `meta`, e uma cópia em tabela seria uma segunda fonte do mesmo dado. Autenticar continua carregando a mesa. Reabrir se a
  medida disser que isso pesa.
- **`Storage` por id.** `exists`, `read`, `create`, `save`, `delete`, `summaries`, `campaigns_in_use`, `count`, `table_ids`.
  Não há caminho de partida. `create` confere o limite de mesas e grava **na mesma transação**, então duas criações juntas não
  passam do limite. `save` é um `UPDATE` e dá `404` se a mesa foi apagada no meio: gravar não a traz de volta.
- **`TableRecords` (`server/records.py`)** liga o banco ao jogo: `load` monta a `Session` com `game.open_save`, e `save` e
  `create` usam `game.build_save`. O caminho da campanha vira relativo à pasta de campanhas na gravação e é revalidado
  (`Catalog.inside`: nunca absoluto, nunca fora da pasta) a cada abertura. Registro ilegível é erro interno, sem o dado.
- **`game/` continua sem banco.** `Session` não tem mais o arquivo como parte obrigatória (`save_path` é opcional e só o
  CLI o usa); `open_save` e `build_save` são puros, e `load_game`/`save_game` por arquivo são invólucros finos para o CLI.
- **Ordem fixa.** O lock da mesa continua por fora; cada leitura e cada gravação é uma transação curta por dentro. O `say`
  segue em três fases (lock, LLM sem lock, lock de novo conferindo a revisão), e nenhuma transação atravessa a chamada ao LLM.
- **Mesa ilegível trava a campanha dela.** `campaigns_in_use` lista o caminho de toda mesa, legível ou não: sem ler, não dá para
  saber que ninguém joga ali.
- **Importar (`devaneio importar`).** Lê os `<id>.json` de antes do banco (da pasta de dados, ou das fontes dadas), valida cada
  um como o servidor faria (`open_save`) e o grava com o mesmo id, tokens e convite e a data do arquivo como `updated_at`.
  Idempotente (pula o que já existe), não altera os originais e recusa com o motivo, sem copiar conteúdo, o que não é mesa
  (solo, JSON quebrado, nome que não é id), tem campanha fora da pasta ou não combina com a campanha e as regras.
  Ao subir, o servidor faz a mesma conta sem gravar (`import_saves(..., apply=False)`) e avisa o que entraria e **lista o que seria
  recusado, com o motivo**, para o aviso não pedir um `importar` que não resolve.

## Próxima fatia

- **3. Exportar, backup e histórico.** `exportar` (sem os hashes de token por padrão), `backup` (API de backup do SQLite,
  sem a chave) e a política de "apagar mesa".
