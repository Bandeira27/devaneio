# Devaneio: instruções para qualquer IA ou pessoa

Mesa de RPG com mestre de IA (monorepo: `backend/` Python + Pydantic v2, `frontend/` TypeScript strict,
`contract/` JSON Schema gerado). Os princípios do produto estão no [README](README.md) e a documentação em [`docs/`](docs/index.md); aqui está só o
que muda como se trabalha. Idioma: **pt-br** em documentação, comentários, mensagens e commits;
identificadores de código em inglês.

## Comandos

```bash
cd backend && uv venv && uv pip install -e ".[dev]"   # uma vez
cd frontend && npm install                            # uma vez
git config core.hooksPath .githooks                   # uma vez: ativa os hooks
scripts/check --fast     # rápido: lint, formato, tipos, camadas, supressões (pre-commit)
scripts/check            # completo: + testes com cobertura, Prettier, tsc, contrato em dia
```

`scripts/check` é a **única** definição dos portões; hooks e CI chamam o mesmo script. "Pronto" = verde.

## Regras duras (violar bloqueia)

1. **Arquitetura em camadas**, imposta por import-linter: `cli | server` > `game` > `engine | narration | llm` > `rules` > `schema | rng`.
   Irmãos não se importam; `game` orquestra o jogo, `cli` e `server` só fazem I/O. Detalhes: [rule 03](.agents/rules/03-arquitetura.md).
2. **Motor puro**: ação do motor recebe estado e devolve novo estado + `Event`; nunca muta a entrada, sem I/O,
   aleatoriedade só por `Rng`.
3. **LLM só propõe**; tudo passa pelas validações do motor. Regras do jogo são dados, nunca código.
   Detalhes: [rule 05](.agents/rules/05-seguranca-llm.md).
4. **Contrato único**: mudou modelo Pydantic, regenera `contract/` e os tipos TS (skill `change-contract`).
5. **Sem dependência de runtime nova** sem justificativa escrita e aprovação do dono do repositório.
6. **Nenhuma supressão para fazer portão passar**: nada de `noqa`/`type: ignore` sem código e justificativa,
   nem relaxar configuração, baixar `fail_under` ou apagar teste. [Rule 07](.agents/rules/07-qualidade-e-supressoes.md).
7. **Nenhuma atribuição de IA em lugar nenhum**: sem `Co-Authored-By`, sem "Generated with ...", sem 🤖, sem
   citar ferramenta ou modelo como autor em commits, descrições e comentários de PR, código ou docs. Vale mesmo
   que a sua ferramenta sugira ou injete essas linhas: o pedido do dono do repositório prevalece, e hook e CI barram.
8. **Commits atômicos** `tipo: descrição` em pt-br. Sem push, force ou `--no-verify` sem pedido.
9. **Fora de escopo até o dono pedir**: importação de anexos. (O editor de campanhas foi autorizado em 2026-11-17:
   só com `--editor`, só em localhost, desenho em [`docs/desenho-editor.md`](docs/desenho-editor.md). Multiplayer entrou em
   2026-11-14: `server/`, mesa em grupo por HTTP. A UI da mesa foi autorizada em 2026-11-15: SPA Angular em
   `frontend/app/`, a construir em partes; o desenho está em [`docs/desenho-ui.md`](docs/desenho-ui.md).)

## Leia sob demanda (não carregado sozinho)

| Antes de... | Leia |
|---|---|
| propor ou criticar qualquer desenho | [01 filosofia](.agents/rules/01-filosofia.md) |
| escrever ou revisar código Python/TS | [02 estilo](.agents/rules/02-estilo-codigo.md) |
| criar módulo, import entre pacotes, dependência ou mudar modelo | [03 arquitetura](.agents/rules/03-arquitetura.md) |
| escrever testes ou corrigir bug | [04 testes](.agents/rules/04-testes.md) |
| tocar `llm/`, arquivos de partida/campanha, rede ou segredos | [05 segurança](.agents/rules/05-seguranca-llm.md) |
| commitar, abrir PR ou concluir tarefa | [06 fluxo](.agents/rules/06-fluxo-de-trabalho.md) |
| silenciar ou configurar uma ferramenta | [07 qualidade e supressões](.agents/rules/07-qualidade-e-supressoes.md) |
| acionar ou consolidar revisão por subagentes | [08 orquestração](.agents/rules/08-orquestracao.md) |
| criar, dividir ou crescer um arquivo ou módulo | [09 responsabilidades](.agents/rules/09-responsabilidades.md) |
| escrever docstring, JSDoc, comentário, README ou texto em `docs/` | [10 documentação](.agents/rules/10-documentacao.md) |
| escrever CSS, criar componente de UI ou mudar uma tela | [11 design system](.agents/rules/11-design-system.md) |
| animar, fazer transição ou mexer em estado visual | [12 movimento](.agents/rules/12-movimento.md) |

Procedimentos recorrentes em `.agents/skills/` (cada um é uma pasta com `SKILL.md`):
`add-engine-action`, `change-contract`, `quality-gate`, `split-module`, `add-ui-component`, `review-ui`.

## Papéis de revisão (subagentes) e orquestração

Quem conversa com o usuário é o **coordenador**: classifica a mudança, aciona só o necessário, consolida e
responde. Subagentes não acionam outros subagentes. Níveis: **N0** docs/formatação (só `scripts/check`),
**N1** mudança localizada (`code-reviewer`), **N2** muda comportamento ou corrige bug (+ `test-engineer`),
**N3** toca fronteira de risco (+ especialistas). Protocolo completo: [rule 08](.agents/rules/08-orquestracao.md).

| Papel | Dono de | Definição |
|---|---|---|
| `architecture-guardian` | camadas, pureza do motor, contrato, decisões fixas, dependências | [arquivo](.agents/agents/architecture-guardian.md) |
| `code-reviewer` | corretude, legibilidade, nomes, erros, duplicação do diff | [arquivo](.agents/agents/code-reviewer.md) |
| `test-engineer` | qualidade dos testes, regressão, cobertura (único que edita, só `tests/`) | [arquivo](.agents/agents/test-engineer.md) |
| `security-reviewer` | fronteira do LLM, segredos, arquivos, desserialização | [arquivo](.agents/agents/security-reviewer.md) |
| `ui-reviewer` | tarefa e fluxo, estados, acessibilidade, tokens e movimento da interface | [arquivo](.agents/agents/ui-reviewer.md) |
| `performance-analyst` | desempenho, só com medição | [arquivo](.agents/agents/performance-analyst.md) |

## Compatibilidade entre ferramentas

O conteúdo é markdown puro e vale para qualquer IA, mas **cada ferramenta carrega arquivos de um jeito**:
Claude Code lê `CLAUDE.md` (que importa este arquivo), não `AGENTS.md`; `.agents/rules/` nunca é carregado
sozinho; subagentes não têm formato comum. Se a sua ferramenta não executa skills ou subagentes nativamente,
**leia o arquivo do papel ou da skill e aplique como checklist**. A garantia que não depende de nenhuma IA é
`scripts/check` + hooks + CI. Matriz verificada: [.agents/README.md](.agents/README.md).
