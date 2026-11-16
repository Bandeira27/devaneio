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

| Grupo              | Tokens                                                                                                                                         |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| **Paleta**         | `smoke`, `sepia`, `ink`, `rose`, `verdigris`, `brick`, `amber`, `dusk`, `stain` (só decoração)                                                 |
| **Superfícies**    | `surface-0` (página), `-1` (cartão), `-2` (hover), `-3` (o que flutua)                                                                         |
| **Papéis**         | `text`, `text-muted`, `text-disabled`, `accent` (+ `hover`, `pressed`, `disabled`), `on-accent`, `ok`, `warn`, `info`, `danger`, `selection`   |
| **Tom de status**  | cada tom tem `-surface`: fundo sobre o qual o texto do tom passa                                                                               |
| **Contorno**       | `line` (decoração), `border-control` (≥ 3:1, carrega significado), `border-disabled`, `focus-ring`                                             |
| **Desbotado**      | `fade-floor-text` (0,65, texto de leitura), `fade-floor-quiet` (0,85, cores de tom), `opacity-stain`                                           |
| **Tipografia**     | famílias (`font-narration`, `font-note`, `font-ui`), tamanhos (`text-*`), `leading-*`, `weight-regular`                                        |
| **Espaço e forma** | `space-1`, `2`, `3`, `4`, `6` e `8`, `radius`, `radius-lg`, `radius-round`, `touch` (44 px), `border-width`, `focus-*`, `size-pip`, `size-dot` |
| **Medida**         | `measure-page`, `measure-table`, `measure-sheet`, `sheet-max-height`                                                                           |
| **Camada**         | `z-base`, `z-raised`, `z-sticky`, `z-overlay`                                                                                                  |
| **Elevação**       | `shadow-float` (folha, diálogo), `shadow-press` (pressionado)                                                                                  |
| **Movimento**      | `duration-*`, `ease-*`, `stagger`, `motion-distance`                                                                                           |

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

Móvel primeiro. Dois pontos de quebra, **fixos e documentados** (CSS não aceita variável em `@media`): **40rem** e
**64rem**. Componentes que mudam com o espaço que recebem usam `@container`. Largura de leitura em `ch`/`measure-*`.
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
| `dv-icon`                                | conjunto fechado de ícones decorativos                                                               |
| `Sheet`, `dv-sheet-head`                 | folha modal que sobe do pé, com saída animada                                                        |

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

## Como mudar ou criar

1. **Valor novo?** Entra em `tokens.css` com o papel comentado e, se for cor, com o par de contraste em `tokens.spec.ts`.
2. **Estilo novo?** Só `var(--dv-...)`; `scripts/check` roda o design-lint.
3. **Componente novo?** Primeiro procure um existente que sirva ([rule 11](../.agents/rules/11-design-system.md)); componente de `shared/ui` entra com a story dos estados.
4. **Movimento novo?** Responda a pergunta da [rule 12](../.agents/rules/12-movimento.md) no PR.

## Aceitação (por componente e por tela)

Teclado completo; foco visível ≥ 3:1; nome acessível; alvo ≥ 44 px nos controles principais (≥ 24 px nos densos);
informação nunca só por cor; `prefers-reduced-motion` respeitado; só tokens; sem rolagem horizontal em 320 px e texto a
200 % sem perda; `h1` por tela; leitor de tela anuncia o que mudou e não repete.
