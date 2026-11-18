# 12. Movimento

Movimento é informação, não enfeite. Detalhes, catálogo e exemplos: [`docs/movimento.md`](../../docs/movimento.md).

## A regra de ouro

Toda animação responde **sim** a pelo menos uma pergunta:

1. Ajuda a entender uma mudança de estado?
2. Comunica uma ação ou a resposta do sistema?
3. Mantém a continuidade entre elementos?
4. Estabelece hierarquia ou profundidade?
5. Torna a interação mais intuitiva?

Sem resposta convincente, a animação não existe. O PR que adiciona movimento diz qual pergunta ele responde.

## Como se escreve

- **Só tokens:** `--dv-duration-{instant,fast,base,slow,narrative,pending}`, `--dv-ease-*`, `--dv-stagger`,
  `--dv-reveal-step` (a pausa entre os itens novos do feed), `--dv-motion-distance`. Nenhuma duração nem curva literal (o design-lint barra).
- **Só o que é barato:** `opacity`, `transform`, cor e contorno. Nunca animar `width`, `height`, `top`, `margin`,
  `max-height` etc. (expandir usa `grid-template-rows` ou `interpolate-size`). Sem `will-change` por padrão.
- **CSS e o que o Angular já traz:** transições e `@keyframes` em CSS; `animate.enter`/`animate.leave` para o que entra e
  sai do template; `withViewTransitions` para rotas. Biblioteca de animação só com justificativa técnica escrita.
- **Nunca atrasa a operação:** o estado final vale na hora; a animação só decora a chegada. Nada que bloqueie clique.
- **Redução de movimento:** os tokens de duração caem para quase zero e a distância para zero em
  `prefers-reduced-motion: reduce` (em `tokens.css`); não há `!important` global. Feedback funcional continua por cor e
  texto. Usando os tokens, a preferência já vale, com duas exceções que o lint barra: animação `infinite` (use
  `var(--dv-iterations-pending)`, que vira 1 com movimento reduzido) e `scroll-behavior: smooth`.
- **Lento só onde é narrativo:** `--dv-duration-narrative` é exclusivo da tinta nova da narração; no máximo um movimento
  narrativo por vez, e lote grande de eventos entra sem escalonamento.

## Proibido

Máquina de escrever na narração, parallax, mancha animada, "levantar" cartão no `hover`, mola/salto, confete, brilho
infinito em carregamento, animar o feed inteiro ao abrir. Carregando usa indicador de pendência que só roda enquanto há
pendência.

## Como se testa

jsdom não executa animação: os testes conferem classe e atributo, e que a remoção de elemento com `animate.leave` não
trava. O visual se confere no catálogo e no navegador, também com movimento reduzido.
