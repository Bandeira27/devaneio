# 11. Design system

Vale para todo o app Angular (`frontend/app`). O visual é o **Desbotado** (fumaça e sépia, narração em IM Fell English,
notas em Special Elite, bordas pontilhadas, o que já passou desbota). Esta rule fixa **como o estilo é escrito**; os
valores, a escala e os exemplos estão em [`docs/design-system.md`](../../docs/design-system.md), e o movimento tem a sua
própria rule ([12](12-movimento.md)).

## Tokens são a fonte única

- Cor, duração, curva, sombra, `z-index`, medida, tamanho de ponto e opacidade vivem em `src/styles/tokens.css`. Os
  estilos só **consomem** `var(--dv-...)`. Cor só em OKLCH e só em `tokens.css`; fora dele não há hex, `rgb`, `oklch`
  nem `px` solto (`rem` e `ch` valem).
- `tools/design-lint.spec.ts` barra: cor, duração e curva literais, `z-index` e sombra literais, `px`, `!important`,
  token inexistente e animação de propriedade que força layout. Exceção só com justificativa na lista do próprio lint.
- Token novo entra com o uso que o motivou, em `tokens.css`, com comentário de papel. Valor que só um componente usa
  e que é geometria dele (uma largura mínima em `rem`) fica no componente; valor que dois usam sobe para token.
- **Contraste é medido, não declarado.** Todo par de cor que carrega informação entra em `tools/tokens.spec.ts` (por
  revisão: o spec lista os pares à mão, nada acusa um par esquecido):
  texto ≥ 4,5:1, contorno de controle, anel de foco e texto desabilitado ≥ 3:1. O que desbota tem piso por papel
  (`--dv-fade-floor-*`): a cor perde contraste mais que a sépia.
- Elevação: o que repousa se separa por superfície e contorno; **sombra só em quem flutua** (folha, diálogo) ou está
  pressionado. Pontilhado é papel/informação; contorno sólido é o que se toca.

## Camadas do CSS

| Camada                  | Onde                                                                 | O que mora                                                |
| ----------------------- | -------------------------------------------------------------------- | --------------------------------------------------------- |
| Tokens                  | `styles/tokens.css`                                                  | valores                                                   |
| Base                    | `styles/base.css`, `fonts.css`                                       | reset, foco, seleção, texto escondido visualmente         |
| Primitivos e tipografia | `styles/primitives.css`, `typography.css`, `layout.css`, `sheet.css` | classes globais `.dv-*` usadas por diretivas e telas      |
| Componente              | `shared/ui/*` (`.css` ao lado)                                       | estilo encapsulado de um componente `dv-*`                |
| Feature                 | `features/*`                                                         | só disposição da tela; nada de cor nem tipografia própria |

## Componentes

- **Reutilize antes de criar.** Componente novo só com **dois ou mais usos reais** ou um problema de UX comprovado;
  abstração genérica demais dificulta o uso. Todo componente de `shared/ui` tem spec, JSDoc ([rule 10](10-documentacao.md))
  e story com os estados (`story()` de `src/app/testing/story.ts`; o teste de fumaça as renderiza).
- **Contrato comportamental:** entradas, saídas, estados, teclado, ARIA, movimento e responsividade estão no JSDoc do
  componente. Estados obrigatórios onde fizerem sentido: repouso, `hover`, `focus-visible`, `active`, `disabled`
  (com motivo), `loading` (`aria-busy`), erro e vazio.
- As stories mostram os estados que o componente controla (repouso, `disabled`, erro, `loading`...). `hover`, `focus-visible`
  e `active` são do navegador e se conferem nele; o catálogo não os força.
- O CDK só entra por `shared/ui` (já imposto pelo ESLint).

## Acessibilidade é critério de aceitação

Vale por componente e por tela, não é uma etapa final: navegação por teclado completa; foco visível; nome acessível;
hierarquia semântica (`h1` por tela, landmarks); alvos de toque ≥ 44 px nos controles principais; informação nunca só
por cor (texto ou ícone junto); `prefers-reduced-motion` respeitado; regiões ao vivo sem anúncio duplicado. A lista
objetiva de conferência está em `docs/design-system.md`.

## Informação para quem joga

A interface fala o vocabulário do jogo. **Não exponha** ids de slug, siglas de atributo (`FOR`), códigos de erro,
revisão, nomes de comando nem texto cru do servidor: traduza. Quem joga não precisa conhecer a estrutura interna. O
rótulo de um botão é o título da folha que ele abre, em verbo no imperativo.
