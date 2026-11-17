# Design system

O visual do app é o **Desbotado**: uma memória meio velha, meio incerta de existir. Este documento é a referência dos
valores e das decisões; as regras de como escrever estilo estão na [rule 11](../.agents/rules/11-design-system.md) e as
de movimento na [rule 12](../.agents/rules/12-movimento.md) (detalhes em [`movimento.md`](movimento.md)). O porquê da
estética e da arquitetura do app está em [`desenho-ui.md`](desenho-ui.md).

## Onde está cada coisa

| O quê                                 | Arquivo                                             |
| ------------------------------------- | --------------------------------------------------- |
| Tokens (a única fonte de valor)       | `frontend/app/src/styles/tokens.css`                |
| Reset, foco, seleção, texto escondido | `styles/base.css`                                   |
| Botão, campo, cartão                  | `styles/primitives.css`                             |
| Título, abertura, nota                | `styles/typography.css`                             |
| Pilha e coluna de página              | `styles/layout.css`                                 |
| Folha                                 | `styles/sheet.css`                                  |
| Componentes `dv-*`                    | `src/app/shared/ui/*`                               |
| Testes de contraste e de regra        | `tools/tokens.spec.ts`, `tools/design-lint.spec.ts` |

## Tokens

Todos começam por `--dv-`. Mudar um valor é mudar o tema inteiro; por isso nenhum estilo escreve valor próprio.

| Grupo              | Tokens                                                                                                                                                                                                                                                    |
| ------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Paleta**         | `sepia`, `ink`, `rose`, `verdigris`, `brick`, `amber`, `dusk`, `stain` (só decoração)                                                                                                                                                                     |
| **Superfícies**    | quatro degraus que sobem de verdade (≥ 1,1:1 entre vizinhos, medido pelo teste de tokens): `surface-0` (fundo do app), `-1` (painel: o que contém controles), `-2` (página: cena, ficha, o que se lê), `-3` (destaque que se sobrepõe: o aviso "N novas") |
| **Papéis**         | `text`, `text-muted`, `text-disabled`, `speaker` (quem fala: tinta), `accent` (rosa: **só ação**; + `hover`, `pressed`, `disabled`), `on-accent`, `ok`, `warn`, `info`, `danger`, `selection`                                                             |
| **Tom de status**  | cada tom tem `-surface`: fundo sobre o qual o texto do tom passa                                                                                                                                                                                          |
| **Contorno**       | `line` (decoração), `border-control` (≥ 3:1, carrega significado), `border-disabled`, `focus-ring`                                                                                                                                                        |
| **Desbotado**      | `fade-floor-text` (0,65, texto de leitura), `fade-floor-quiet` (0,85, cores de tom), `opacity-stain`                                                                                                                                                      |
| **Tipografia**     | famílias (`font-narration`, `font-note`, `font-ui`), tamanhos (`text-display`, `-title`, `-section`, `-narration`, `-ui`, `-note`), `tracking-label`, `leading-*`, `weight-regular`                                                                       |
| **Espaço e forma** | `space-1`, `2`, `3`, `4`, `6` e `8`, `radius`, `radius-lg`, `radius-round`, `touch` (44 px), `border-width`, `focus-*`, `size-pip`, `size-dot`                                                                                                            |
| **Medida**         | `measure-page`, `-table`, `-feed`, `-wide` (o contêiner do app), `-sheet`, `-dialog`, `-ornament`, `rail-width`, `sheet-max-height`                                                                                                                       |
| **Camada**         | `z-base`, `z-raised`, `z-sticky`, `z-overlay`                                                                                                                                                                                                             |
| **Elevação**       | `shadow-float` (folha, diálogo), `shadow-press` (pressionado)                                                                                                                                                                                             |
| **Movimento**      | `duration-*`, `ease-*`, `stagger`, `motion-distance`                                                                                                                                                                                                      |

### Contraste

O contraste é medido por `tools/tokens.spec.ts` (WCAG): texto ≥ 4,5:1 sobre as superfícies, texto de cada tom sobre o
fundo do tom, texto do botão de acento em repouso, `hover` e pressionado, texto selecionado; contorno de controle, anel
de foco e texto desabilitado ≥ 3:1. O que desbota é medido **por papel** sobre a superfície 0, que é onde o feed mora.
`--dv-line` e `--dv-stain` são decoração e ficam abaixo disso de propósito: nada essencial depende deles.

## Elevação

O Desbotado é plano. Quem **repousa** se separa por superfície (0 a 3) e por contorno: o **pontilhado** é papel e
informação, o **sólido fino** é o que se toca. **Sombra** só em quem flutua (folha, diálogo) e no estado pressionado,
sempre pelos tokens `shadow-*`. Nada de gradiente de cor.

## Tipografia

Narração e títulos em IM Fell English (itálico nos títulos, ≥ 15 px: a fonte é irregular em tamanho pequeno), notas
mecânicas em Special Elite, controles na fonte do sistema. Informação operacional ("já agiu", "fora de combate") não
vai em nota fraca: vira selo com texto.

## Layout e responsividade

Móvel primeiro. Os pontos de quebra são **fixos e documentados** (CSS não aceita variável em `@media`): **64rem** (duas
colunas: a lateral da mesa, a home e a entrada); **90rem** (três painéis da mesa: o contêiner e as laterais mudam). O
contêiner do app em tela larga é `--dv-measure-wide` (hoje o cabeçalho e as manchas; as telas passam a ocupá-lo com
painéis lado a lado), em vez de esticar a coluna do celular. Medidas de leitura: `measure-page`, `-table`,
`-feed`, `-wide`, `-sheet`, `-dialog`, `-ornament`. Componentes que mudam com o espaço que recebem usam `@container`. Largura de leitura em `ch`/`measure-*`.
Áreas seguras (`env(safe-area-inset-*)`) e `dvh` onde há barra fixa.

## Componentes

Todos em `frontend/app/src/app/shared/ui/`, com spec e story. O contrato (entradas, estados, teclado, ARIA, movimento)
está no JSDoc de cada um.

| Componente                               | Para quê                                                                                             |
| ---------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `dvButton` (diretiva)                    | botão: `dvBlocked` (bloqueado com motivo, continua focável), `dvLoading` (em envio), `:active`, tons |
| `dv-field` + `dvInput`                   | rótulo, dica e erro de `input`, `select` e `textarea`                                                |
| `dv-stepper`, `dv-copy-field`, `dv-pips` | valor com − e +, texto para copiar, pontos de vida (mudança animada)                                 |
| `dv-notice`                              | aviso com ícone: informação, confirmação, atenção, erro; dispensável                                 |
| `dv-badge`                               | selo de estado curto, com texto, tom e ícone; `pending` pulsa                                        |
| `dv-state`                               | carregando, vazio, erro ou indisponível, com ação opcional                                           |
| `dv-key-value`                           | pares rótulo e valor (`dl`)                                                                          |
| `dv-disclosure`                          | detalhe que abre e fecha (sobre `details`)                                                           |
| `dv-choice`                              | escolha única em cartões grandes (rádios nativos)                                                    |
| `dv-character-card`                      | a ficha (pontos de vida, atributos, inventário): na folha "Ficha" e no painel da mesa larga          |
| `dv-steps`                               | os passos de um caminho curto (Mesa, Personagem, Jogar), com o atual marcado                         |
| `dv-brand`                               | a marca: selo com a inicial e o nome (cabeçalho `md`, abertura `lg`)                                 |
| `dv-ornament`                            | filete com losango: abre tela e separa capítulos (decoração)                                         |
| `dv-icon`                                | conjunto fechado de ícones decorativos                                                               |
| `Sheet`, `dv-sheet-head`                 | folha modal que sobe do pé, com saída animada                                                        |

**Folhas:** todas têm a mesma forma: cabeçalho (título igual ao rótulo do botão que a abriu e fechar por ícone), corpo e
rodapé `.dv-sheet__foot` com a ação primária à direita. No celular sobem do pé; na tela larga (≥ 64rem) viram um
diálogo centralizado de até `--dv-measure-dialog`. Ações que gastam a vez (`Ir`, `Atacar`) pedem a confirmação dentro
da própria folha. Escolhas curtas (habilidade, dificuldade, alvo, arma, modificador) usam `dv-choice`; botões em envio
usam `dvLoading` e mantêm o rótulo.

**As telas de entrada** (entrar, convite, personagem) usam o **palco** `.dv-stage`: no celular uma coluna; a partir de
64rem, o contexto à esquerda (passos, título em `.dv-display`, texto, ornamento, resumo da ficha) e a tarefa à direita.
A **home** é capa + painel: à esquerda a apresentação, a premissa da campanha e as mesas guardadas ("Continuar" na mais
recente), à direita criar mesa e "Tenho um convite" (recolhido). O cabeçalho e todas essas telas se alinham ao mesmo
contêiner (`--dv-measure-wide`).

**Hierarquia sem peso de fonte** (as duas fontes só têm peso 400): escala (`.dv-title`, `.dv-section`, marca em `text-display`),
rótulos em caixa-alta com espaçamento (`tracking-label`), superfície, ornamento e cor com papel único (rosa = ação e
seleção (o cartão escolhido de `dv-choice` também usa o rosa); tinta = quem fala). Três tipos de bloco: **painel** (`.dv-card`, controles), **página** (`.dv-card.dv-card--page`, o que se
lê: mais clara, com filete de tinta no topo) e **sem caixa** (narração, grupo).

O **cartão** e a **lista** não são componentes: são as classes `.dv-card` e `.dv-stack` (não havia comportamento a
encapsular). Não há _tabs_ nem _toast_ (o feedback é contextual).

## Catálogo (Storybook)

```bash
cd frontend/app
npm run storybook          # abre o catálogo em http://localhost:6006
npm run build-storybook    # gera storybook-static/ (roda no scripts/check completo)
```

Cada componente de `shared/ui` (e os da mesa que valem catalogar) tem um `*.stories.ts` ao lado, com os estados. As
stories se escrevem com o helper `story(imports, template)` de `src/app/testing/story.ts`: ele guarda a receita, e
`src/app/testing/stories.spec.ts` renderiza **todas** no Vitest, então uma story quebrada falha o teste (e
`tools/stories-list.spec.ts` falha se um arquivo de stories novo não estiver na lista do spec). As páginas **Design/Tokens**
e **Design/Movimento** vêm de `src/app/design/`. A aba de acessibilidade (axe) mostra as violações de cada story. Stories não
entram no build do app (`tsconfig.app.json`) nem exigem JSDoc.

## A mesa

Pensada pela tarefa: quem joga lê a história o tempo todo e age uma vez por turno.

- **Celular:** uma coluna. Situação do turno ("Sua vez de agir", "Você já agiu · falta Zed"), cena (com a descrição sempre à vista, sem accordion)
  e grupo, depois a história; a **barra de ações fica fixa no pé**: as ações do turno (Ir,
  Testar, Atacar e, com LLM, Falar) em cima e, numa linha de apoio menor, Ficha e Comando. A mesa mede a barra e publica
  `--dv-dock-height` na raiz; o `scroll-padding-bottom` do documento faz o fim da história e o que ganha foco pararem
  acima dela. Quem leu mais acima vê "N novas" quando chega algo; tocar leva ao fim e o foco vai para a história.
- **Altura baixa (celular em paisagem, ou zoom alto; `max-height: 30rem`):** as ações do turno e as de apoio dividem uma
  só linha e os avisos da barra ficam limitados (4rem), para ela não tomar a tela (medido: de 34% para 20% de 360 px).
- **Tela larga (≥ 64rem):** situação, cena e grupo à esquerda e rolam com a página; só a barra de ações fica presa no
  topo dessa coluna, com a história (42rem) ao lado. A página rola: **não há rolagem aninhada**.
- **Tela muito larga (≥ 90rem): três painéis.** Cena e grupo à esquerda, a história no meio, e à direita a **ficha de quem
  joga** (visível e recolhível) (`dv-character-card`, o mesmo conteúdo da folha "Ficha") com as ações presas logo abaixo; o botão
  "Ficha" some. O contêiner do app cresce com o terceiro painel (`--dv-measure-wide` muda em 90rem).
- **A história:** o turno é um cabeçalho de capítulo (ornamento e o número em itálico); a narração é o protagonista, e a
  linha de como foi resolvido fica logo abaixo dela, sempre à vista, em tinta e fonte de nota (sem accordion).
  As **saídas da cena** são botões: tocar abre a folha de `Ir` já na confirmação do destino.
- **Ordem do HTML = ordem de leitura e de foco** (situação e cena, história, minha ficha, ações), sem `order` para reordenar. O
  "Pular para as ações" (`.dv-skip`, visível só com foco) leva ao primeiro botão que ainda age. O `.shell` usa
  `overflow: clip` (não `hidden`) para não quebrar o `sticky`.
- Sem conexão, sessão vencida ou mesa sumida, as ações ficam **bloqueadas com o motivo** (em vez de falhar com erro cru).
- O leitor de tela só anuncia o que chega depois do carregamento; dano e cura levam ícone e texto, não só cor; o turno
  atual diz "agora".

## Como mudar ou criar

1. **Valor novo?** Entra em `tokens.css` com o papel comentado e, se for cor, com o par de contraste em `tokens.spec.ts`.
2. **Estilo novo?** Só `var(--dv-...)`; `scripts/check` roda o design-lint.
3. **Componente novo?** Primeiro procure um existente que sirva ([rule 11](../.agents/rules/11-design-system.md)); componente de `shared/ui` entra com a story dos estados.
4. **Movimento novo?** Responda a pergunta da [rule 12](../.agents/rules/12-movimento.md) no PR.

## Aceitação (por componente e por tela)

Teclado completo; foco visível ≥ 3:1; nome acessível; alvo ≥ 44 px nos controles principais (≥ 24 px nos densos);
informação nunca só por cor; `prefers-reduced-motion` respeitado; só tokens; sem rolagem horizontal em 320 px e texto a
200 % sem perda; `h1` por tela; leitor de tela anuncia o que mudou e não repete.
