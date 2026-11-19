# O banco do servidor

**Status: aprovado em 2026-11-19; a fatia 1 (base do banco e configuração do LLM) está implementada. As fatias 2 (mesas,
partidas e tokens) e 3 (exportar, backup e histórico) seguem em aberto.**

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

## Próximas fatias

- **2. Mesas, partidas e tokens no banco.** Tabelas `tables` e `players`, `Storage` por id de mesa, `campaign_path`
  relativo à pasta de campanhas, importação idempotente das partidas JSON (`importar`), sem tocar nos arquivos originais.
- **3. Exportar, backup e histórico.** `exportar` (sem os hashes de token por padrão), `backup` (API de backup do SQLite,
  sem a chave) e a política de "apagar mesa".
