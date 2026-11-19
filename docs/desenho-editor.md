# Desenho: editor de campanhas

Quinto passo do [rumo de extensibilidade](rumo-extensibilidade.md), liberado pelo dono em 2026-11-17 (regra 9 do
`AGENTS.md`) e implementado em quatro partes (API, base, marcos e fatos, prévia). O autor típico não é técnico e, antes dele, só criava campanha editando JSON, que só é validado quando uma mesa a
carrega. O editor deixa criar e ajustar a campanha por formulários, com a validação em português ao vivo, os avisos de
autoria e uma prévia do que o jogador e o LLM veem. Um formato só: o editor lê e escreve os mesmos `campaigns/*.json`.

## Decisões

- **Sempre ligado, só da própria máquina.** Sem login: a defesa é o lugar, conferida em cada pedido (rule 05, item 25):
  conexão de loopback, sem cabeçalho de proxy, `Host` local e `Origin` próprio. Vale mesmo com o servidor aberto à rede
  (`--host 0.0.0.0`): os jogadores entram pelo convite, o anfitrião edita por `localhost`, no mesmo servidor. De fora,
  `/editor/*` é `404`. `--sem-editor` desliga (era `--editor` que ligava; a flag deixou de existir em 2026-11-19, quando o
  editor, centro do produto, deixou de ficar escondido). **Proxy ou túnel na frente do servidor** fazem todo pedido parecer local e a guarda não os cobre
  de todo (um `nginx` local não manda cabeçalho de encaminhamento): quem expõe o servidor assim usa `--sem-editor`.
  Abrir pelo endereço da rede (`192.168.x.x`) não vale como "a
  própria máquina": para editar, abra por `localhost`.
- **Abrir sem argumentos.** `./devaneio` (ou `devaneio` / `python -m devaneio.server`), dentro do projeto, usa `campaigns/`, `mesas/` e o build do app
  (se existir) e abre o navegador em `localhost`; `--sem-navegador` não abre.
- **Nova campanha ou cópia.** As mesas guardam o caminho da campanha e a relêem ao carregar, então o editor nunca
  sobrescreve uma campanha que já tem mesa (`409`, "salve uma cópia"). Campanha sem mesa pode ser regravada.
- **Escopo completo** da campanha: título e premissa, locais, NPCs, facções, marcos e fatos, com as condições (`at_location`,
  `npc_down`, `beat_done`, `turn_at_least`, `check_passed`) escolhidas em listas guiadas.
- **O servidor valida; o app só mostra.** `POST /editor/validate` devolve os erros em português (estrutura traduzida,
  integridade, cruzamento com o sistema e a narração) e os avisos de autoria (`game/authoring.check_content`). Só se grava
  sem erro.
- **Prévia.** A campanha como o jogador a vê (`CampaignView`) e o que o LLM recebe, sem e com segredos, mais o tamanho do
  contexto do copiloto frente ao teto. Não grava nada.
- Nenhuma dependência nova e nenhum código do autor é executado: o editor só escreve JSON.

O servidor só faz I/O: a conferência da campanha (`game.check_campaign_data`) e a prévia (`game.preview_contexts`) vivem em
`game`, e `server/editor.py` as traduz para os modelos da API.

## API (`server/editor.py`)

| Rota                                           | Faz                                                                                              |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `GET /editor/campaigns`                        | `[{id, title, writable}]`; `writable` = nenhuma mesa usa o arquivo                               |
| `GET /editor/campaigns/{id}`                   | a `Campaign` inteira                                                                             |
| `POST /editor/validate` `{campaign}`           | `{ok, errors: [{path, message}], findings: [{level, text}]}`                                     |
| `POST /editor/campaigns` `{campaign}`          | cria (`409` se o id existe); `201 {id, title, writable}`                                         |
| `PUT /editor/campaigns/{id}` `{campaign}`      | regrava (`409` com mesa; o id não muda)                                                          |
| `GET /editor/systems` e `/editor/systems/{id}` | os sistemas de regras disponíveis e o `RulesView` (habilidades e dificuldades)                   |
| `POST /editor/preview` `{campaign}`            | `{player, llm, llm_secrets, copilot_chars, copilot_limit}`                                       |
| `GET /editor/campaigns/{id}/tables`            | `[{table_id, phase, host_name, players, updated_at}]`: as mesas que usam a campanha, sem segredo |
| `DELETE /editor/tables/{id}`                   | encerra a mesa: apaga o arquivo e acorda quem espera (`{table_id}`)                              |
| `POST /editor/tables/{id}/host-access`         | reemite o acesso do anfitrião: `{table_id, player_id, token, invite_code}`                       |

Com `--sem-editor`, ou de fora da máquina do servidor, tudo isso é `404`. O corpo vai até 512 KiB. O catálogo passa a ver a campanha salva sem reiniciar.

## Partes

1. **API** (este desenho e o `server/editor.py`).
2. **App, base** (feito): lista, nova e copiar; visão geral, locais, NPCs e facções; validação ao vivo e gravar; ids que
   acompanham o nome e atualizam as referências quando renomeados; remover pede confirmação e solta o que apontava para o
   item. O app vive em `features/editor/`; os componentes novos são `dv-select` e `dv-list-editor`, e a folha de confirmar
   subiu para `shared/ui` (`dv-confirm-sheet`). O servidor é quem valida; o app só mostra.
3. **App, marcos e fatos** (feito): marcos com requisitos e condições de começar e de terminar; fatos com o assunto
   (local, NPC, facção ou marco) e as condições de revelar. O editor de condições é uma lista de linhas (tipo fechado e o
   item que ele cita, ou o número do turno; `check_passed` usa as habilidades do sistema escolhido); todas as condições
   de uma lista precisam valer, e lista vazia quer dizer "só o anfitrião move". Os erros de integridade e os avisos de
   autoria que o servidor devolve em frases (`marco 'x', ...`) aparecem dentro do item.
4. **Prévia** (feito): a aba mostra o que o jogador vê no começo da partida (`CampaignView`), o contexto que o mestre de IA
   recebe só com o público e o que recebe com `--segredos-no-llm`, e o tamanho do contexto do copiloto frente ao teto
   ("cabe com folga", "perto do limite" a partir de 80%, "passa do limite"). É pedida ao servidor quando a campanha não
   tem erros, fica marcada como antiga depois de uma edição e se atualiza pelo botão. Tudo é texto.

## Alternativa futura: dois listeners

A guarda atual confere a origem de cada pedido, e um proxy ou túnel local a engana (ver Decisões). Se o Devaneio um dia
for exposto na internet de verdade, a separação mais forte é o servidor, no mesmo processo Python, escutar em **duas
portas**: a pública, onde as rotas `/editor/*` não existem, e uma só em `127.0.0.1`, onde o editor vive. Quem garante a
separação passa a ser o sistema operacional, não a conferência de endereço e cabeçalho. Foi descartada por ora porque:

- o anfitrião passaria a usar duas portas, e o link de convite, montado a partir do endereço que o navegador mostra,
  sairia errado quando gerado pela porta local (o servidor precisaria informar o endereço público);
- a guarda por pedido já cobre o uso real (rede de casa, acesso por `localhost`) e `--sem-editor` cobre o resto;
- sem programa externo (Node, `nginx`) e sem dependência nova, a instalação continua a mais simples possível.

## As mesas, vistas pelo servidor (`server/editor_tables.py`)

O servidor é a fonte da verdade de quais mesas existem; o navegador só guarda o token de quem entrou
(`localStorage`, por origem). Antes, a Visão Geral confiava no navegador e o editor no servidor, e as duas telas se
contradiziam (testar em dois navegadores deixava mesas que nenhum dos dois via, travando a campanha). Agora:

- **Listar** lê só `campaign_path` e `table` de cada arquivo (`saved_table_summary`), sem carregar campanha nem regras.
  Expõe id, fase, nome do anfitrião, número de jogadores e a data do arquivo; nunca hash, convite nem notas.
- **Encerrar** apaga o arquivo sob o lock da mesa e acorda quem espera (`announce_change`); a volta do long-poll é `404`.
  A entrada em memória da mesa fica: quem espera compara a versão dela, e esquecê-la a faria voltar a zero.
- **Assumir como anfitrião** troca o token e o convite do anfitrião (o servidor guarda só hash, então reemite).
  O token antigo deixa de valer, e os links de convite já enviados também. A resposta mostra os novos uma única vez.
- As três rotas ficam sob `/editor/*`: herdam o `404` fora da máquina, `Host` e `Origin`.
- No app, o aviso "esta campanha já tem mesa", a Visão Geral e a página Mesas usam a lista do servidor; fora da máquina
  do servidor (`404`) caem de volta na lista do navegador.

**Limite conhecido:** o token de **jogador** continua só no navegador dele. Perdê-lo exige entrar de novo com o convite e
deixa o personagem antigo órfão. Um link de retorno por jogador, gerado pelo anfitrião, é a ideia para o futuro.

## Fora do editor

Editar sistemas de regras e pacotes de narração, importar anexos, versionar e migrar conteúdo, edição colaborativa e
desfazer além de descartar as alterações.
