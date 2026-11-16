# 10. Documentação

Vale para Python e TypeScript. Idioma: pt-br. Esta rule diz **onde cada tipo de texto mora e como é escrito**; o que o
`ruff` e o ESLint já impõem não é repetido aqui.

## Docstring ou JSDoc: o contrato

Todo módulo, classe, função e membro **público** tem um bloco de documentação que diz o que ele é e o que promete:

- a primeira linha é uma frase que descreve, no presente ("Devolve...", "Valida...", "Estado da mesa ao vivo");
- depois, só o que o nome e o tipo não dizem: quando falha, invariantes, efeitos colaterais, o que acontece em borda;
- não repita o nome nem o tipo (`"""Retorna o nome."""` em `get_name`). Sem informação nova, não escreva: a ausência de
  docstring num item público óbvio é melhor que uma de enchimento, e o ruff pede só a primeira linha.

**Python:** docstring estilo Google. As seções `Args:`, `Returns:` e `Raises:` (em inglês, porque as ferramentas as
reconhecem) entram **só quando acrescentam** o que o tipo não diz (unidade, intervalo, qual erro e quando). Docstring de
módulo curta: o que o módulo é e, se houver, a gramática ou o formato.

```python
def classify_outcome(margin: int, outcomes: Outcomes) -> CheckOutcome:
    """Converte a margem de um teste (resultado menos dificuldade) em um dos quatro graus."""
```

**Modelos Pydantic:** a docstring de um modelo (e a `description` de um campo) vira `description` no JSON Schema de
`contract/` e comentário nos tipos TypeScript gerados. Escreva-a para quem usa o contrato, sem detalhe interno, e
regenere o contrato ao mudá-la (skill `change-contract`).

**TypeScript:** JSDoc `/** ... */` sem tipos (o TypeScript já os tem); `@param` e `@returns` só quando acrescentam algo.

```ts
/** Relê a mesa e a cena. Chamadas feitas durante uma leitura em voo recebem uma leitura nova, iniciada depois do pedido. */
refresh(): Promise<void> {
```

## Comentário: só o porquê, curto e local

`#` e `//` servem para **uma nota curta (uma ou duas linhas) ao lado do código** que explica uma restrição ou uma armadilha que o código
sozinho não mostra ("antes da carga: uma gravação no meio deixaria a versão adiante da visão").

- Nunca um bloco de três ou mais linhas. Se precisa de um parágrafo, é docstring/JSDoc do item que ele descreve.
- Nunca decisão de produto ou história ("decisão do dono", "como era antes"). Isso mora em `docs/desenho-*` e no
  histórico do git.
- Nunca o "como" da linha. Se o código precisa de comentário para ser entendido, troque o nome ou extraia uma função.
- Diretiva de ferramenta (`noqa`, `ts-expect-error`) segue a [rule 07](07-qualidade-e-supressoes.md).

## Onde cada coisa mora

| Texto                           | Lugar                                                | Tom                                                                 |
| ------------------------------- | ---------------------------------------------------- | ------------------------------------------------------------------- |
| O que o projeto é e como rodar  | `README.md`                                          | acolhedor e simples, para quem acabou de chegar; sem jargão no topo |
| Como as coisas funcionam hoje   | `docs/` por assunto (índice em `docs/index.md`)      | claro e direto                                                      |
| Por que foram feitas assim      | `docs/desenho-*.md` e `docs/rumo-extensibilidade.md` | explica a decisão e o que ficou de fora                             |
| Como contribuir (regras duras)  | `AGENTS.md` e `.agents/rules/`                       | objetivo                                                            |
| Contrato de um item de código   | docstring / JSDoc                                    | técnico e curto                                                     |
| Uma armadilha no meio do código | comentário de uma linha                              | curto                                                               |

README e textos de `docs/` voltados a quem chega falam como uma pessoa falaria: frases curtas, sem tom de relatório
corporativo, termos técnicos só quando necessários e explicados na primeira vez. Referência técnica não entra no README:
vai para `docs/`.

## Quando muda a documentação

Junto com o código, no mesmo commit ([06](06-fluxo-de-trabalho.md)): ação do motor ou comando do CLI em
`docs/motor.md`, rota em `docs/api-http.md`, configuração do LLM em `docs/llm.md`, passo a passo de rodar no README.
