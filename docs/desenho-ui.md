# Desenho: UI da mesa

A API da mesa está completa e tipada, mas o único cliente era `curl` e os testes. Este documento fixa as decisões da
UI antes do código. A entrega é em partes: o **backend da UI** (rota de regras, `TableView.you`, servir o front com CSP),
o **app do jogador** (Angular), o painel do anfitrião com o copiloto e, depois, o editor de campanhas.

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
- **Estado:** signals em serviços por feature. **Um tema**, com todas as cores em OKLCH num arquivo de tokens.
- **Botões** para as ações, com chat opcional para digitar comandos; o texto livre pelo LLM segue como ação.
- **Mesa primeiro, editor depois.** O editor (depois) só existe com `--editor` e só em localhost.

## Estética: Desbotado

Uma memória desbotada, "meio velha, meio incerta de existir", como a palavra devaneio. Fumaça e sépia, IM Fell English na
narração e nos títulos, Special Elite nas notas mecânicas, controles na fonte do sistema, bordas pontilhadas, manchas
discretas, sem sombra nem gradiente.

- **Incerteza só na atmosfera, nunca na informação.** Resultado de teste, hp, botões e erros ficam nítidos.
- **Memória por idade:** a cena atual é nítida e os turnos passados desbotam, com piso de opacidade 0,65. Texto novo se
  "revela" com um fade curto (`prefers-reduced-motion` desliga).
- **Cores em OKLCH**, sem hex, com variações por cor relativa. O contraste é medido por teste (WCAG >= 4,5:1 nos pares
  essenciais): os valores da primeira ideia falhavam (tinta velha 4,1:1, rosa de poeira 3,9:1 sobre a fumaça) e
  foram ajustados.
- No painel do anfitrião (depois), fato oculto aparece como tinta borrada e "se revela" quando o motor o revela. O jogador
  nunca vê lacuna de fato oculto: isso revelaria que ele existe.

## Arquitetura do app

Convenção de mercado para Angular standalone: `core/`, `shared/`, `features/` e `layout/`, organizada por
funcionalidade.

```
frontend/app/src/
  styles/        tokens.css (OKLCH), base.css, fontes
  app/
    core/        singletons sem UI: api (HttpClient + interceptor de Bearer + ApiError), session, live (long-poll)
    shared/      ui/ (componentes dv-* sobre o CDK), game/ (lógica pura: commands, feed, rules), util/
    layout/      shell
    features/    home/  join/  character/  table/   (host/ e editor/ depois)
```

`features` e `layout` usam `shared` e `core`; `shared` e `core` não dependem de `features`, de `layout` nem um do outro;
uma feature não importa outra; só `shared/ui` importa o CDK. Isso será imposto por ESLint (configurado no primeiro
passo do app, antes de qualquer tela), como o import-linter faz no backend.

## Dependências novas (regra 5)

Só do front, em `frontend/app/`; o backend continua só com a stdlib.

| Dependência | Por quê |
|---|---|
| `@angular/*` (core, common, router, platform-browser, compiler, build, cli, compiler-cli) | o framework escolhido |
| `@angular/cdk` | comportamento acessível (overlay, diálogo, foco) por baixo dos componentes `dv-*` |
| `rxjs` | exigido pelo Angular (HttpClient e router) |
| Vitest (e o ambiente DOM que o Angular usar) | executor de testes padrão do Angular |
| `eslint`, `typescript-eslint`, `@angular-eslint/*` | camadas, proibições de segurança e acessibilidade de template |
| `@fontsource/im-fell-english`, `@fontsource/special-elite` | as duas fontes (licença OFL) copiadas pelo build: nenhuma carga de CDN externa |

A lista final (com versões) sai do primeiro passo do app, que fixa a versão do Angular e do TypeScript compatível.

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

Criar mesa, convite (link com endereço editável, que avisa quando for `localhost`), entrar mostrando o **aviso de
privacidade do LLM**, criar personagem (nome e atributos do sistema), e a mesa: feed ao vivo e ações em botões (`Ir`,
`Testar`, `Atacar`, `Ficha`, `Falar`, `Comando`). O anfitrião usa a mesma tela e cria o próprio personagem; os comandos só
dele ficam para o painel do anfitrião.

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
