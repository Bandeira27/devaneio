# Desenho: painel do anfitrião

O anfitrião joga na mesma tela dos jogadores, mas só ele vê a campanha inteira (notas privadas, fatos ocultos, marcos
pendentes) e só ele dá `fim`, `ferir`, `curar`, `descansar`, `marco` e `revelar`. Hoje isso é digitar no "Comando". O painel
mostra esse lado e transforma os comandos em botões. Ele é uma **barra lateral da própria mesa**: o anfitrião age sem
tirar os olhos da história. Não muda backend nem contrato: usa `GET .../campaign` (a `Campaign` inteira), o `GameState`
inteiro de `TableView.state`, os comandos do anfitrião e `POST .../copilot` ([`desenho-copiloto.md`](desenho-copiloto.md)).

## Decisões

- **Barra lateral, não rota.** O painel abre à direita da mesa (`/#/mesa/:id`), por um botão "Anfitrião" no cabeçalho,
  só para o anfitrião. A rota antiga `/#/mesa/:id/anfitriao` continua existindo só para não quebrar links: redireciona
  para a mesa com a barra aberta. Quem não é anfitrião nunca vê o botão (o servidor já responde `403`; esconder é
  conforto, não segurança).
- **Duas formas, o mesmo conteúdo.** Em tela larga é uma barra ao lado do feed (região `complementary`, sem tirar o
  foco da história). Em tela estreita é um **bottom sheet**, sobre a folha que o app já usa (CDK); aí é modal, com
  foco preso, Esc fecha e o foco volta ao botão que abriu. O ponto de corte vem dos tokens de layout, não de um
  número solto.
- **Fechada por padrão.** O conteúdo é privado e a tela pode estar à vista do grupo (compartilhamento, projetor). A
  barra só abre quando o anfitrião pede, e o estado aberto ou fechado vale só para a página, sem `localStorage` nem URL.
  Fechar não apaga nada: o painel é uma visão do mesmo estado.
- **Usa o `TableStore` da mesa.** A barra mora em `features/table/host/` (uma feature não importa outra) e lê o store que
  a `TablePage` já tem: nenhum segundo fluxo ao vivo, nenhuma segunda leitura da campanha além da própria. A resposta do
  copiloto e a pergunta em andamento ficam num estado da página, e não no componente do painel, porque no bottom sheet
  fechar destrói o componente e a resposta não pode se perder.
- **Cinco blocos, em seções.** Copiloto, ferramentas do turno, marcos, fatos, NPCs e locais, em seções recolhíveis (a
  barra é estreita). O bloco **Partida** fica fixo no topo, sempre visível.
- **Botões montam linhas de comando** (as mesmas de `shared/game/commands.ts`); quem decide é o motor. Nada novo no
  servidor.
- **Tudo é texto.** Notas privadas, descrições e a resposta do LLM aparecem como texto (nunca `innerHTML`); a resposta do
  copiloto fica só na memória da página, sem `localStorage`, sem URL e sem eco no mural.
- **A mesa continua sendo a tela.** Com a barra aberta, o dock de ações e o feed seguem funcionando; as confirmações de
  Concluir, Falhar, Revelar, Descansar e Encerrar abrem como folha por cima de tudo, também em tela larga.
- **Avisos vivos não dependem da barra aberta.** "A resposta do copiloto chegou" é anunciado mesmo com a barra fechada;
  o botão "Anfitrião" mostra um indicador textual de que há resposta nova.

## A partida (sala de espera, pausa e fim)

A mesa nasce numa **sala de espera**, e a história só começa quando o anfitrião clica em **Iniciar campanha** (precisa de
ao menos um personagem; o botão diz o motivo enquanto estiver bloqueado). Na sala, convidados entram e criam
personagem. No painel, o bloco **Partida** mostra o tempo de jogo e tem **Pausar** (trava os jogadores; o anfitrião
continua) e **Retomar**, e **Encerrar** (definitivo: pede confirmação e diz que ninguém mais age). O tempo só corre
enquanto a partida roda. As regras de cada fase estão em [`api-http.md`](api-http.md#fases-da-mesa).

## Blocos

- **Copiloto.** Pergunta de até 500 caracteres numa linha só (o servidor recusa quebra de linha: o que for colado em várias linhas vira espaço), resposta síncrona. O foco vai à resposta quando ela chega e o aviso vivo diz só que chegou. Estados: LLM desligado (explica), pensando, e as
  recusas `409 copilot_busy`, `429 copilot_rate_limited`, `422 context_too_large`, `502` (mensagens já em
  `core/api/api-failure.ts`). Aviso fixo de que ele vê a campanha inteira, segredos inclusive, e que a resposta só o
  anfitrião lê. Sem memória entre perguntas.
- **Ferramentas do turno.** Fim do turno e Descansar (com confirmação: mexem com o grupo todo), Ferir e Curar (alvo,
  quantidade e fonte opcional, em folha). O anfitrião pode ferir NPC escondido: isso não aparece para os jogadores.
- **Marcos.** Título, status em selo (texto e ícone), requisitos, notas privadas; Ativar, Concluir e Falhar bloqueados com
  o motivo conforme o status; Concluir e Falhar pedem confirmação, e cada botão leva o nome do marco.
- **Fatos.** Texto, de quem fala, "Oculto" ou "Revelado no turno N" e o botão Revelar (com confirmação: não tem volta). O oculto aparece como tinta
  borrada, que clareia em hover, foco e toque; o selo "Oculto" sempre está lá, e o leitor de tela lê o texto normalmente.
  Ao revelar, o fato "se revela" (mudança de estado que o anfitrião precisa notar: [`movimento.md`](movimento.md)).
- **NPCs e locais.** Só leitura: local, hp, vivo ou caído, disposição (número; o limiar de hostilidade não vem em `RulesView`) e as notas privadas.

## Fora do painel

Editor de campanhas, facções, edição de qualquer dado, histórico do copiloto e resposta em streaming.
