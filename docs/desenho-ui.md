# Desenho: UI da mesa

A API da mesa está completa e tipada, mas o único cliente era `curl` e os testes. Este documento fixa as decisões da
UI antes do código. A entrega é em partes: o **backend da UI** (rota de regras, `TableView.you`, servir o front com CSP),
o **app do jogador** (Angular), a barra lateral do anfitrião com o copiloto e, depois, o editor de campanhas.

## Estado do design

O app do jogador tem design system próprio (tokens, componentes com contrato, catálogo em Storybook, movimento com
regra), mesa pensada pela tarefa e entrada curta. O redesenho seguinte reorganizou a informação e usou a tela larga:
transição entre telas (a página vira, cabeçalho parado, folha de espera), fundação visual (degraus de superfície, escala,
marca, ornamento), entrada em dois painéis (contexto e tarefa) e mesa em até três painéis (cena e grupo, história, ficha
e ações). Os textos de referência: [`design-system.md`](design-system.md),
[`movimento.md`](movimento.md) e [`padroes-de-interacao.md`](padroes-de-interacao.md). A revisão de UI tem papel
(`ui-reviewer`) e skill (`review-ui`). O selo de desfecho do teste (ícone, texto e tom na nota mecânica) já está no feed. O editor de campanhas está em [`desenho-editor.md`](desenho-editor.md); a barra lateral do
anfitrião está em [`desenho-painel-anfitriao.md`](desenho-painel-anfitriao.md).

## Decisões

- **Angular + TypeScript**, SPA mobile-first (celular na rede local; computador também), em `frontend/app/`.
- **`frontend/app/` tem `package.json` próprio.** O Angular exige o TypeScript da faixa dele; `frontend/` fixa o TS 7
  só para gerar os tipos do contrato e não muda.
- **O servidor Python serve o build** pela mesma origem (`--web DIR`): sem CORS e mantendo a defesa de CSRF por
  `application/json`.
- **Roteamento por hash** (`/#/mesa/...`): o servidor não precisa de fallback de SPA e o código do convite fica no
  fragmento, que nunca chega ao servidor nem ao log.
- **Token no navegador** (`Authorization: Bearer`, `localStorage`), sem cookie. Risco aceito: exposição a XSS, mitigada
  por CSP restrita, escape do Angular e proibição de `innerHTML` e `bypassSecurityTrust*` por lint (que entra com o app).
- **Estado:** signals em serviços por feature, sem camada de _use-case_ à parte: a regra do jogo mora no backend, e a SPA
  só mostra o estado e manda a ação. **Um tema**, com todas as cores em OKLCH num arquivo de tokens.
- **Serviço e store.** Tudo o que se injeta é um serviço (`@Injectable`), nomeado pelo papel, **sem o sufixo `Service`**
  (`ApiClient`, `ServerTables`, `CampaignCatalog`). Um **store** (`*Store`) é o serviço que guarda o **estado de uma tela
  ou de uma feature em signals**: a página o fornece em `providers` e o descarta com ela (`EditorStore`,
  `CreateTableStore`), salvo os de `core/` (`SessionStore`), que são da aplicação toda. Ação que orquestra várias
  chamadas e tem regra própria no cliente (arquivar uma mesa, gravar) não fica engordando o store: vai para um serviço
  da feature, que o store ou a página chama (`EditorTables`). O critério de quando dividir é o da
  [rule 09](../.agents/rules/09-responsabilidades.md).
- **Botões** para as ações, com chat opcional para digitar comandos; o texto livre pelo LLM segue como ação.
- **Mesa primeiro, editor depois.** O editor só atende a máquina do servidor (localhost), sem flag.
- **Configuração do mestre de IA** (`/configuracao`, ligada na tela inicial): guarda o LLM da máquina (endereço, modelo, tempo e chave) e, como o editor, só abre por `localhost`. Vale na hora; a chave só entra e nunca volta. Ver [`llm.md`](llm.md) e [`desenho-banco.md`](desenho-banco.md).

## Navegação por campanha

`/` lista as campanhas em cards; `/c/:campaignId` é o quadro da campanha (`layout/campaign-shell`, com a barra lateral) e
tem como filhas a visão geral, as mesas (`/mesas`) e o roteiro (`/roteiro/...`, o editor de campanhas, só para quem abre por localhost).
A mesa em jogo (`/mesa/:tableId/...`) e as telas de entrada ficam fora do quadro, em tela cheia. As páginas de dentro
leem o `campaignId` da rota de fora (`paramsInheritanceStrategy: 'always'`). Cada mesa guardada neste aparelho anota o id da
campanha (`StoredTable.campaignId`; as antigas casam pelo título); o catálogo de campanhas e a pergunta "o editor atende
este navegador?" vivem num serviço só (`core/catalog`). **Quais mesas existem** é do servidor: `core/tables` pergunta a ele (só da máquina do servidor; de fora vem `404` e a lista volta a ser só a do navegador), e o `localStorage` guarda apenas o token de quem entrou. O desenho de interação está em [`padroes-de-interacao.md`](padroes-de-interacao.md).

## Fases da mesa

A mesa tem uma **fase** (`TableView.phase`: `lobby`, `running`, `paused`, `ended`; ver [`api-http.md`](api-http.md#fases-da-mesa)).
A `TablePage` mostra a **sala de espera** (`features/table/components/lobby`) na fase `lobby` e o jogo nas outras; a mudança
de fase é uma ação do `TableStore` (`lifecycle`) e vira evento no log, então o fluxo ao vivo relê a mesa sozinho. A fase
entra nos bloqueios de ação (`actBlock`, em `shared/game/rules.ts`). Criar uma mesa leva a `/mesa/:id/personagem` e, salvo o
personagem, a `/mesa/:id` (a sala, último passo do caminho de entrada); o anfitrião pode pular o personagem.

## Estética: Desbotado

Uma memória desbotada, "meio velha, meio incerta de existir", como a palavra devaneio. Fumaça e sépia, IM Fell English na
narração e nos títulos, Special Elite nas notas mecânicas, controles na fonte do sistema, bordas pontilhadas, manchas
discretas. Nada de gradiente de cor; sombra só no que flutua (folha, diálogo) ou está pressionado: o que repousa se separa
por superfície e contorno (ver [`design-system.md`](design-system.md)).

- **Incerteza só na atmosfera, nunca na informação.** Resultado de teste, hp, botões e erros ficam nítidos.
- **Memória por idade:** a cena atual é nítida e os turnos passados desbotam. O piso de opacidade é **por papel**: 0,65
  para o texto de leitura e 0,85 para o que é cor de tom (nota, falante, dano, cura), porque a cor perde mais contraste
  que a sépia. Texto novo se "revela" com um fade (o movimento reduzido o encurta: [`movimento.md`](movimento.md)).
- **Cores em OKLCH**, sem hex, com variações por cor relativa. O contraste é medido por teste (WCAG >= 4,5:1 nos pares
  essenciais): os valores da primeira ideia falhavam (tinta velha 4,1:1, rosa de poeira 3,9:1 sobre a fumaça) e
  foram ajustados.
- Na barra do anfitrião, fato oculto aparece como tinta borrada e "se revela" quando o motor o revela. O jogador
  nunca vê lacuna de fato oculto: isso revelaria que ele existe.

## Arquitetura do app

Convenção de mercado para Angular standalone: `core/`, `shared/`, `features/` e `layout/`, organizada por
funcionalidade.

```
frontend/app/src/
  styles/        tokens.css (OKLCH), base.css, fontes
  app/
    core/        singletons sem UI: api (HttpClient + interceptor de Bearer + ApiError), session, live (long-poll)
    shared/      ui/ (componentes dv-* sobre o CDK), game/ (lógica pura: commands, feed, rules, cena, nomes, convite...)
    features/    home/  campaign/  join/  invite/  character/  table/  editor/   (home/ lista as campanhas em cards; campaign/ é a visão geral e as mesas de uma campanha; table/host/ é a barra lateral do anfitrião; editor/ é o roteiro)
    layout/      shell/ (cabeçalho e página)  campaign-shell/ (a barra lateral de uma campanha)
```

`features` e `layout` usam `shared` e `core`; `shared` e `core` não dependem de `features`, de `layout` nem um do outro;
uma feature não importa outra; só `shared/ui` importa o CDK. Isso é imposto por ESLint
(`frontend/app/eslint.config.mjs`, provado por `tools/eslint-rules.spec.ts`), como o import-linter faz no backend.
`src/app/testing/` é infraestrutura de teste e fica fora das camadas.

## Dependências novas (regra 5)

Só do front, em `frontend/app/`; o backend continua só com a stdlib.

| Dependência                                                                               | Por quê                                                                                                                                                                       |
| ----------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `@angular/*` (core, common, router, platform-browser, compiler, build, cli, compiler-cli) | o framework escolhido                                                                                                                                                         |
| `@angular/cdk`                                                                            | comportamento acessível (overlay, diálogo, foco) por baixo dos componentes `dv-*`                                                                                             |
| `rxjs`                                                                                    | exigido pelo Angular (HttpClient e router)                                                                                                                                    |
| `vitest` 5 e `jsdom` 30                                                                   | executor de testes padrão do Angular e o DOM dele                                                                                                                             |
| `tslib`                                                                                   | exigido pelo Angular                                                                                                                                                          |
| `eslint`, `@eslint/js`, `typescript-eslint`, `angular-eslint`                             | camadas, proibições de segurança e acessibilidade de template                                                                                                                 |
| `eslint-plugin-jsdoc` (só dev)                                                            | impõe JSDoc nos exports do app e proíbe tipo dentro do JSDoc ([rule 10](../.agents/rules/10-documentacao.md)); compatível com ESLint 10 e TypeScript 6, nada vai ao navegador |
| `storybook`, `@storybook/angular-vite`, `@storybook/addon-a11y` (só dev, 10.6.5 fixada)   | catálogo vivo dos componentes e dos tokens, com checagem de acessibilidade (axe) por story; resultado do spike na nota abaixo da tabela                                       |
| `@fontsource/im-fell-english`, `@fontsource/special-elite`                                | as duas fontes (licença OFL) copiadas pelo build: nenhuma carga de CDN externa                                                                                                |

**Spike do Storybook (2026-11-16):** funciona com Angular 22, TypeScript 6 e zoneless; tema, fontes e a folha (CDK)
renderizam; build em ~10 s e ~8,6 MB; 0 vulnerabilidades em produção (as 7 moderadas de dev já existiam, são do eslint);
nenhum script de instalação novo; +135 pacotes de dev (React, interno do Storybook, e `@angular/animations`, exigido como
peer e não usado pelo app). Telemetria desligada (`core.disableTelemetry`).

As versões ficam fixadas em `frontend/app/package-lock.json`: Angular 22 e TypeScript ~6.0 (a faixa que o Angular
aceita). **Duas versões de TypeScript convivem:** `frontend/` usa o 7 só para os tipos do contrato e o `tsc` dele não
valida o app; o app é validado pelo `ng build`.

## Segurança no navegador

- **CSP** em tudo que o servidor serve de arquivo (o valor exato está em `server/static.py`, `CSP`, com o teste que o
  prova): scripts, fontes, imagens e conexões só de `'self'`, sem plugins, sem `<base>` externo e sem moldura, mais
  `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY` e `nosniff`. `'unsafe-inline'` em estilos é um risco
  aceito: o Angular injeta estilos de componente em tempo de execução.
- **Estáticos confinados** à pasta do build: sem `..`, sem symlink para fora, sem diretório, MIME por lista fechada.
- **O front renderiza tudo como texto.** O servidor remove caracteres de controle de nomes e falas, mas não escapa
  marcação: um nome `<img onerror=...>` precisa aparecer como texto.
- **Pré-condição do editor:** validar o cabeçalho `Host` (DNS rebinding contra um servidor local sem login).

## Telas da primeira versão (jogador)

Criar mesa, sala de espera com o convite (link com endereço editável, que avisa quando for `localhost`), entrar mostrando o **aviso de
privacidade do LLM**, criar personagem (nome e atributos do sistema), e a mesa: feed ao vivo e ações em botões (`Ir`,
`Testar`, `Atacar`, `Ficha`, `Falar`, `Comando`). O anfitrião usa a mesma tela e cria o próprio personagem; os comandos só
dele ficam para a barra lateral do anfitrião.

## Limites conhecidos

- A carga inicial do feed pega os últimos 50 eventos; histórico mais antigo fica fora (o anfitrião tem o `log`).
- Cliente que desiste de um long-poll deixa a thread do servidor esperando até 30 s; o cliente mitiga com `wait` curto,
  backoff e um laço por aba.
- Sem teste ponta a ponta automatizado: há testes de integração por feature com HTTP simulado e verificação manual.
- HTTP em claro na rede local, como hoje.
- O aviso de privacidade do LLM (`TableView.llm.notice`) só chega depois de entrar, pois a leitura da mesa exige o
  token. Ele aparece na criação do personagem e na mesa (em `<details>`), não antes do nome. Mostrá-lo antes pediria
  um endpoint novo, sem token, que descreva só o LLM da mesa.
- `Falar` e `Comando` esperam a resposta do servidor (o LLM pode levar segundos): o dock mostra "O mestre está pensando…"
  e desabilita as ações. Em `stale_revision` o cliente relê e repete uma vez; qualquer outro erro vira texto na tela.
