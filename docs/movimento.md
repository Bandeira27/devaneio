# Movimento

Movimento é informação: ajuda a entender o que mudou, não enfeita. A regra está em [`12-movimento.md`](../.agents/rules/12-movimento.md);
aqui estão o catálogo, os tokens e os limites. Os valores vivem em `frontend/app/src/styles/tokens.css`.

## A pergunta

Toda animação responde sim a pelo menos uma: (1) ajuda a entender uma mudança de estado, (2) comunica uma ação ou
resposta do sistema, (3) mantém a continuidade entre elementos, (4) estabelece hierarquia ou profundidade, (5) torna a
interação mais intuitiva. Sem resposta, não existe. Nunca atrasa a operação: o estado final vale na hora.

## Tokens

| Token                     | Valor                 | Uso                               |
| ------------------------- | --------------------- | --------------------------------- |
| `--dv-duration-instant`   | 80 ms                 | pressionar                        |
| `--dv-duration-fast`      | 140 ms                | estado de controle, saída         |
| `--dv-duration-base`      | 220 ms                | entrada, expandir/recolher        |
| `--dv-duration-slow`      | 360 ms                | folha, mudança de contexto        |
| `--dv-duration-narrative` | 600 ms                | só a tinta nova da narração       |
| `--dv-ease-standard`      | `(0.2, 0, 0, 1)`      | estados                           |
| `--dv-ease-decelerate`    | `(0, 0, 0, 1)`        | o que entra                       |
| `--dv-ease-accelerate`    | `(0.3, 0, 1, 1)`      | o que sai                         |
| `--dv-ease-emphasized`    | `(0.05, 0.7, 0.1, 1)` | folha e diálogo                   |
| `--dv-stagger`            | 60 ms                 | escalonamento (no máximo 3 itens) |
| `--dv-motion-distance`    | 0,25 rem              | deslocamento de entrada           |

Com `prefers-reduced-motion: reduce` os tokens de duração caem para 1 ms, o escalonamento para 0 e a distância para 0.

## Catálogo

| Movimento                            | Onde                                                 | Pergunta | Duração e curva                        |
| ------------------------------------ | ---------------------------------------------------- | -------- | -------------------------------------- |
| Pressionar                           | botões                                               | 2, 5     | `instant`, `standard`                  |
| Estado de campo e controle           | foco, erro, `hover`                                  | 1        | `fast`, `standard`                     |
| Entrada e saída de aviso e pendência | avisos, "enviando…"                                  | 1, 2, 3  | `base` ao entrar, `fast` ao sair       |
| Folha e diálogo                      | ações                                                | 3, 5     | `slow`, `emphasized` (sai mais rápido) |
| Expandir e recolher                  | detalhes, cena                                       | 1, 3     | `base` (sem animar `height`)           |
| **Tinta nova**                       | evento ou fala que chegou **depois** do carregamento | 1, 3, 4  | `narrative`, `decelerate`              |
| Envelhecimento                       | opacidade por idade                                  | 4        | `slow` ao mudar o turno                |
| Mudança de hp                        | pontos de vida                                       | 1, 2     | `base`                                 |
| Cópia feita                          | campo de cópia                                       | 2        | `fast`                                 |
| Troca de rota                        | páginas                                              | 3        | `base` (`withViewTransitions`)         |
| Pendência                            | botão em envio, "mestre pensando"                    | 1, 2     | pontos de fumaça, só enquanto pendente |

Estado atual do app: pressionar e estados de botão, entrada e saída de avisos e pendências (`dv-enter`/`dv-leave`), folha (`dv-sheet-in`/`-out`, com fundo no mesmo ritmo), mudança de hp, cópia, pendência (`dv-pulse`), cross-fade de rotas e a tinta nova (`reveal` do feed, só no que chegou depois do carregamento) existem. Os tokens ainda sem uso estão numa lista de espera no `design-lint.spec.ts`, que só pode encolher.

## Rejeitado

Máquina de escrever na narração (atrasa a leitura), parallax e manchas animadas (decoração), "levantar" cartão no
`hover` (cartão não é clicável), mola e salto, confete, brilho infinito em carregamento, animar o feed inteiro ao abrir.

## Limites técnicos

- Só `opacity`, `transform`, cor e contorno. O design-lint barra animar propriedade que força layout.
- Entrada e saída de elementos do template usam `animate.enter`/`animate.leave` do Angular; a saída espera o fim da
  animação (limite de 4 s) e **só alcança elementos do template**: a folha (CDK) tem tratamento próprio.
- jsdom não anima: testes conferem classe e atributo.
