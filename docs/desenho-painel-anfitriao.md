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

## Blocos

- **Copiloto.** Pergunta de até 500 caracteres, resposta síncrona. Estados: LLM desligado (explica), pensando, e as
  recusas `409 copilot_busy`, `429 copilot_rate_limited`, `422 context_too_large`, `502` (mensagens já em
  `core/api/api-failure.ts`). Aviso fixo de que ele vê a campanha inteira, segredos inclusive, e que a resposta só o
  anfitrião lê. Sem memória entre perguntas.
- **Ferramentas do turno.** Fim do turno e Descansar (com confirmação: mexem com o grupo todo), Ferir e Curar (alvo,
  quantidade e fonte opcional, em folha). O anfitrião pode ferir NPC escondido: isso não aparece para os jogadores.
- **Marcos.** Título, status em selo (texto e ícone), requisitos, notas privadas; Ativar, Concluir e Falhar bloqueados com
  o motivo conforme o status.
- **Fatos.** Texto, de quem fala, "Oculto" ou "Revelado no turno N" e o botão Revelar. O oculto aparece como tinta
  borrada, que clareia em hover, foco e toque; o selo "Oculto" sempre está lá, e o leitor de tela lê o texto normalmente.
  Ao revelar, o fato "se revela" (mudança de estado que o anfitrião precisa notar: [`movimento.md`](movimento.md)).
- **NPCs e locais.** Só leitura: local, hp, vivo ou caído, "hostil" (pelo limiar do sistema) e as notas privadas.

## Fora do painel

Editor de campanhas, facções, edição de qualquer dado, histórico do copiloto e resposta em streaming.
