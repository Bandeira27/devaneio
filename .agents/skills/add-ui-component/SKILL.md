---
name: add-ui-component
description: Use ao criar ou mudar um componente de UI do app Angular (frontend/app/src/app/shared/ui), do contrato e dos tokens à story, ao spec e à documentação, com acessibilidade e movimento como critério de aceitação.
---

# Criar um componente de UI

Aplica as rules [11](../../rules/11-design-system.md) e [12](../../rules/12-movimento.md). Componente novo é exceção, não
reflexo: o contrato do que já existe cobre quase tudo.

## Passos

1. **Procure antes.** Existe um componente, uma diretiva ou uma classe `.dv-*` que sirva (ou que sirva estendida)? O
   componente novo só se justifica com **dois ou mais usos reais** ou um problema de UX comprovado. Divisor e lista, por
   exemplo, são classes, não componentes.
2. **Três arquivos, sempre:** `nome.ts`, `nome.html` e `nome.css`, com `templateUrl` e `styleUrl`; nada de `template:` ou
   `styles:` inline, nem num componente de uma linha.
   **Escreva o contrato** no JSDoc do componente ([rule 10](../../rules/10-documentacao.md)): o que é; entradas; saídas;
   estados (repouso, `focus-visible`, `active`, `disabled` ou bloqueado com motivo, `loading`, erro, vazio, no que fizerem
   sentido); teclado; papel ARIA; movimento; comportamento em tela estreita.
3. **Use só tokens** (`var(--dv-...)`). Valor novo entra em `src/styles/tokens.css` com o papel comentado; cor nova, com o
   par de contraste em `tools/tokens.spec.ts`. `scripts/check` roda o design-lint.
4. **Semântica antes de ARIA:** elemento nativo (`button`, `details`, `input type=radio`, `dl`) e só o ARIA que falta.
   Informação nunca só por cor: texto ou ícone junto. Alvo de toque ≥ 44 px nos controles principais.
5. **Movimento só com pergunta respondida** (rule 12), com os tokens `--dv-duration-*` e `--dv-ease-*`; só `opacity`,
   `transform` e cor. Entrada e saída do template: `animate.enter`/`animate.leave` com `dv-enter`/`dv-leave`.
6. **Spec** ao lado (`*.spec.ts`): o contrato inteiro (entradas, saídas, estados, ARIA, teclado). jsdom não anima: confira
   classe e atributo.
7. **Story** ao lado (`*.stories.ts`) com `story(imports, template)` de `src/app/testing/story.ts`, uma por estado que o
   componente controla. Inclua o arquivo em `src/app/testing/stories.spec.ts` (`tools/stories-list.spec.ts` falha se faltar).
8. **Conferência:** `scripts/check` completo; no navegador (ou no catálogo: `npm run storybook`) em 375, 768 e 1280 px,
   com teclado e com movimento reduzido; a aba de acessibilidade do catálogo sem violação.
9. **Documente** o que mudou em `docs/design-system.md` (e em `docs/movimento.md` se criou movimento).

## Armadilhas

- `aria-disabled` não impede clique: use `dvBlocked`/`dvLoading` do botão (engolem o clique na fase de captura) em vez de
  `disabled` quando o foco não pode se perder.
- `animate.leave` só alcança elementos do template; o painel do CDK tem tratamento próprio (`Sheet`).
- Input com alias é barrado pelo ESLint: nomeie a propriedade (`dvBlocked`), não use `alias`.
- Template e estilo em arquivo próprio (`nome.html` e `nome.css`, com `templateUrl` e `styleUrl`), sempre: o ESLint barra
  `template:` e `styles:` inline. O design-lint lê os `.css` do componente como qualquer outro.
- Token declarado e sem uso fica na lista de espera do design-lint, que só pode encolher.
