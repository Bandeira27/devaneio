# Desenho: editor de campanhas

Quinto passo do [rumo de extensibilidade](rumo-extensibilidade.md), liberado pelo dono em 2026-11-17 (regra 9 do
`AGENTS.md`). O autor típico não é técnico e hoje só cria campanha editando JSON, que só é validado quando uma mesa a
carrega. O editor deixa criar e ajustar a campanha por formulários, com a validação em português ao vivo, os avisos de
autoria e uma prévia do que o jogador e o LLM veem. Um formato só: o editor lê e escreve os mesmos `campaigns/*.json`.

## Decisões

- **Só com `--editor` e só em localhost.** Sem login: a defesa é o lugar (rule 05, item 25). O servidor se recusa a subir
  com `--editor` fora de loopback e confere `Host` e `Origin`.
- **Nova campanha ou cópia.** As mesas guardam o caminho da campanha e a relêem ao carregar, então o editor nunca
  sobrescreve uma campanha que já tem mesa (`409`, "salve uma cópia"). Campanha sem mesa pode ser regravada.
- **Escopo completo** da campanha: título e premissa, locais, NPCs, facções, marcos e fatos, com as condições (`at_location`,
  `npc_down`, `beat_done`, `turn_at_least`, `check_passed`) escolhidas em listas guiadas.
- **O servidor valida; o app só mostra.** `POST /editor/validate` devolve os erros em português (estrutura traduzida,
  integridade, cruzamento com o sistema e a narração) e os avisos de autoria (`game/authoring.check_content`). Só se grava
  sem erro.
- **Prévia.** A campanha como o jogador a vê (`CampaignView`) e o que o LLM recebe, sem e com segredos, mais o tamanho do
  contexto do copiloto frente ao teto. Não grava nada.
- Nenhuma dependência nova e nenhum código do autor é executado: o editor só escreve JSON.

## API (`server/editor.py`)

| Rota                                           | Faz                                                                            |
| ---------------------------------------------- | ------------------------------------------------------------------------------ |
| `GET /editor/campaigns`                        | `[{id, title, writable}]`; `writable` = nenhuma mesa usa o arquivo             |
| `GET /editor/campaigns/{id}`                   | a `Campaign` inteira                                                           |
| `POST /editor/validate` `{campaign}`           | `{ok, errors: [{path, message}], findings: [{level, text}]}`                   |
| `POST /editor/campaigns` `{campaign}`          | cria (`409` se o id existe); `201 {id, title, writable}`                       |
| `PUT /editor/campaigns/{id}` `{campaign}`      | regrava (`409` com mesa; o id não muda)                                        |
| `GET /editor/systems` e `/editor/systems/{id}` | os sistemas de regras disponíveis e o `RulesView` (habilidades e dificuldades) |
| `POST /editor/preview` `{campaign}`            | `{player, llm, llm_secrets, copilot_chars, copilot_limit}`                     |

Sem `--editor`, tudo isso é `404`. O corpo vai até 512 KiB. O catálogo passa a ver a campanha salva sem reiniciar.

## Partes

1. **API** (este desenho e o `server/editor.py`).
2. **App, base:** lista, nova e copiar; locais, NPCs e facções; validação ao vivo e salvar.
3. **App, marcos e fatos** com o editor de condições.
4. **Prévia** e fechamento da documentação.

## Fora do editor

Editar sistemas de regras e pacotes de narração, importar anexos, versionar e migrar conteúdo, edição colaborativa e
desfazer além de descartar as alterações.
