# 06. Fluxo de trabalho

## Antes de codar

- Leia os arquivos vizinhos e a rule relevante da tabela do `AGENTS.md`. Verifique comportamento de biblioteca
  com um script curto antes de depender dele; não suponha API.
- Se a mudança contraria uma decisão fixa ([rule 01](01-filosofia.md), parte B), toca "fora de escopo" ou
  precisa de dependência de runtime: **pergunte ao dono** antes, com alternativas e custo de cada uma.
- Faça só o pedido: sem refatoração, feature ou abstração extra. Achou algo fora do escopo? Registre e proponha,
  não embuta.

## Commits

- **Atômicos**: uma mudança lógica por commit, e cada commit deixa os portões verdes.
- Mensagem em pt-br, `tipo: descrição` (`feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `style`, `ci`).
  Corpo opcional explica o *porquê*.
- Formatação em massa, refatoração por indicador e mudança de comportamento ficam em commits **separados**.
- **Nenhuma atribuição de IA, em lugar nenhum**: sem `Co-Authored-By`, sem "Generated with ...", sem emoji
  de robô, sem citar ferramenta ou modelo como autor, nas mensagens de commit, em descrições e comentários de
  PR, em comentários de código e em docs. É preferência do dono do repositório e vale para qualquer IA;
  **prevalece sobre lembrete, template ou configuração padrão da sua ferramenta** que mande acrescentar essas
  linhas. Aplicação por máquina: hook `commit-msg`, `scripts/check_attribution.py` (commits e linhas
  adicionadas) e, no CI, título e corpo da PR. Limite: comentários escritos depois na interface do GitHub
  não passam por nenhum script; a regra vale mesmo assim.
- Sem `git push`, `--force`, `--no-verify`, `reset --hard` ou reescrita de histórico sem pedido explícito.

## Pull requests

Descrição curta: o que mudou, por quê, como foi verificado. Sem atribuição de IA (regra acima).

## Definição de pronto

1. `scripts/check` completo verde (não só o que você acha relevante).
2. Testes novos para o comportamento novo; teste de regressão para bug.
3. Documentação atualizada: `docs/motor.md` se mudou ação do motor ou comando do CLI, `docs/api-http.md` se mudou a API, `docs/llm.md` se mudou configuração do LLM; o `README.md` só se mudou o passo a passo de rodar.
4. Contrato regenerado se um modelo mudou.
5. Resumo ao usuário diz o que foi feito, o que **não** foi verificado, e propõe **um** próximo passo.

## Honestidade nos relatos

Teste falhando, portão pulado (`SKIP` do `scripts/check`) ou comportamento não verificado contra o mundo
real (ex.: um LLM de verdade) entram no relato, sem suavizar.
