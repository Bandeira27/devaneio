# Desenho: painel do anfitrião

O anfitrião joga na mesma tela dos jogadores, mas só ele vê a campanha inteira (notas privadas, fatos ocultos, marcos
pendentes) e só ele dá `fim`, `ferir`, `curar`, `descansar`, `marco` e `revelar`. Hoje isso é digitar no "Comando". O painel
é a tela que mostra esse lado e transforma os comandos em botões. Não muda backend nem contrato: usa `GET .../campaign`
(a `Campaign` inteira), o `GameState` inteiro de `TableView.state`, os comandos do anfitrião e
`POST .../copilot` ([`desenho-copiloto.md`](desenho-copiloto.md)).

## Decisões

- **Rota própria**, `/#/mesa/:id/anfitriao`, com link "Anfitrião" no cabeçalho da mesa só para o anfitrião. O segredo não
  divide a tela com a história que o grupo pode estar vendo. Quem não é anfitrião volta para a mesa (o servidor já
  responde `403`; a guarda é conforto, não segurança).
- **Vive em `features/table/host/`**: uma feature não importa outra, e o painel reaproveita o `TableStore` (foto da mesa,
  regras, campanha, `run(line)`). A página provê o próprio `TableStore`, que morre com ela (um `providers` de rota não é
  destruído ao sair, e o fluxo ao vivo ficaria rodando).
- **Cinco blocos**: copiloto, ferramentas do turno, marcos, fatos, NPCs e locais.
- **Botões montam linhas de comando** (as mesmas de `shared/game/commands.ts`); quem decide é o motor. Nada novo no
  servidor.
- **Tudo é texto.** Notas privadas, descrições e a resposta do LLM aparecem como texto (nunca `innerHTML`); a resposta do
  copiloto fica só na memória da página, sem `localStorage`, sem URL e sem eco no mural.

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
