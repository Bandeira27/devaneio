# 08. Orquestração de subagentes

Texto normativo. Os papéis estão em [`.agents/agents/`](../agents); o resumo, no `AGENTS.md`.

## Coordenador

É o **agente principal da sessão** (qualquer ferramenta ou modelo): o que conversa com o usuário. Só ele
decide quem acionar, consolida e responde. **Subagentes não acionam outros subagentes nem conversam entre si**;
devolvem achados ao coordenador. Em ferramenta sem subagentes, o coordenador aplica cada papel como checklist,
lendo `.agents/agents/<papel>.md` em sequência, com o mesmo protocolo.

## 1. Acionamento proporcional

O coordenador classifica a mudança **antes** de acionar e registra a classificação no relatório.
Rode `scripts/check` primeiro: o que ele pega não precisa de revisor.

| Nível | Critério objetivo                                                                           | Quem entra                        |
| ----- | ------------------------------------------------------------------------------------------- | --------------------------------- |
| N0    | só docs/comentários, renomeação sem efeito, formatação                                      | ninguém; `scripts/check` basta    |
| N1    | mudança localizada num pacote, sem alterar comportamento público, contrato nem dependências | `code-reviewer`                   |
| N2    | muda comportamento observável ou corrige bug                                                | `code-reviewer` + `test-engineer` |
| N3    | toca uma fronteira de risco (abaixo)                                                        | N2 + especialistas da fronteira   |

Fronteira de risco → especialista:

- novo pacote ou módulo; import novo entre pacotes; modelo Pydantic ou `contract/` → `architecture-guardian`
- `llm/`; carga ou escrita de arquivos (`SaveFile`, campanhas); `subprocess`/`urlopen`; segredos →
  `security-reviewer`
- dependência nova → `security-reviewer` **e** `architecture-guardian`
- tela, componente de UI, estilo ou movimento em `frontend/app` (a partir de N2) → `ui-reviewer`
- estado, `rng`, expressões, laço quente, ou queixa de lentidão → `performance-analyst`, **somente com medição
  em mãos**

Máximo recomendado: **3 agentes por mudança**; acima disso o coordenador explica por quê. Não acione todos
por reflexo: custo e ruído crescem mais rápido que o valor.

## 2. Tarefas que exigem colaboração

| Tarefa                                 | Agentes                                                         |
| -------------------------------------- | --------------------------------------------------------------- |
| mudança de contrato                    | `architecture-guardian` + `test-engineer`                       |
| qualquer mudança em `llm/`             | `security-reviewer` + `architecture-guardian` + `test-engineer` |
| dependência nova                       | `architecture-guardian` + `security-reviewer`                   |
| primeira ação do motor de um tipo novo | `architecture-guardian` + `test-engineer`                       |
| mudança de tela ou componente de UI    | `code-reviewer` + `ui-reviewer`                                 |

## 3. Comunicação e compartilhamento de descobertas

Via coordenador, sempre. Cada agente recebe um **briefing**: diff ou arquivos, nível atribuído, rules relevantes
e, do segundo agente em diante, os achados **já consolidados** (para não repetir). Agentes independentes entre si
rodam em paralelo; o `test-engineer` roda depois que o código de produção está estável.

## 4. Formato único de achado

Todo agente devolve achados assim (um por item):

```
id: <papel>-<n>
severidade: bloqueia | recomenda | nota
onde: arquivo:linha
evidência: o que foi observado ou medido (comando, saída, trecho)
regra: rule ou princípio violado (ex.: 03-arquitetura; DRY)
ação: o que fazer
```

Fora do escopo do agente: ele **não julga**; emite `encaminhar: <agente> — <o quê>`. O coordenador roteia
(aciona o agente indicado ou, se for decisão de produto, pergunta ao usuário).

## 5. Bloquear ou recomendar

- **bloqueia**: viola regra dura (rules 03, 05, 07), quebra `scripts/check`, falha de segurança explorável,
  contradiz decisão fixa sem aprovação do dono, correção de bug sem teste de regressão.
- **recomenda**: melhoria justificável (inclui refatoração motivada por indicador de tamanho).
- **nota**: observação sem ação exigida.

Só `bloqueia` impede concluir. O resto vai para o relatório e o usuário decide.

## 6. Consolidação

O coordenador remove duplicatas, agrupa por arquivo, ordena por severidade e entrega **um relatório**:
nível atribuído; agentes acionados (e os pulados, com motivo); achados; conflitos resolvidos e pendentes.
Nunca repassa a saída bruta de vários agentes.

## 7. Sobreposição

Cada tema tem **um dono** (tabela do `AGENTS.md`). Se dois agentes sinalizam o mesmo ponto, vale o do dono;
o outro vira "ver achado X". Sobreposição que se repete é defeito da definição dos agentes: corrija em
`.agents/agents/`, não caso a caso.

## 8. Conflito de recomendações

Precedência fixa: **segurança > decisões fixas de arquitetura > corretude > testes > legibilidade > desempenho.**

- Níveis diferentes: vence o de maior precedência; o coordenador registra a concessão feita.
- Mesmo nível, ou envolve decisão de produto ou escopo: **pergunta ao usuário**, com as opções e o custo de
  cada; nunca decide em silêncio.
- Pedido explícito do usuário prevalece sobre recomendação, exceto sobre `bloqueia` de segurança, que o
  coordenador reitera uma vez e registra.
