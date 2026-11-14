# 01. Filosofia de programação

Dois blocos com natureza diferente. **Princípios gerais** orientam o raciocínio: servem para pensar e
justificar, não são checklist mecânico, e cada um tem um custo quando aplicado fora de hora.
**Decisões do Devaneio** são escolhas de produto já tomadas: não se reabrem sem o dono do repositório.

## Parte A. Princípios gerais

Ao propor ou criticar uma mudança, nomeie o princípio que a motiva **e** o custo de aplicá-lo.
"Violou DRY" sem mostrar conhecimento duplicado não é um achado válido. Se dois princípios conflitam,
vence a opção que um leitor novo entende mais rápido.

**KISS.** A solução mais simples que resolve o problema de agora. Desempata quase tudo.
*Atrapalha* quando "simples" significa omitir uma invariante (validar `rng_draws` parece burocracia até o
replay divergir) ou copiar e colar.

**YAGNI.** Não construa para um futuro hipotético; a lista de "fora de escopo" do `AGENTS.md` é YAGNI com dono.
*Atrapalha* quando reverter custa caro depois (contrato público, formato de partida salva, ids): aí pense um
passo à frente no *desenho*, sem implementar o passo seguinte.

**DRY.** O alvo é duplicação de *conhecimento* (uma regra, uma fórmula, um esquema com duas fontes), não
de texto parecido. Abstraia na terceira repetição, e só se as três mudarem pelo mesmo motivo.
*Atrapalha* quando funde coisas que evoluem separadas (narração e motor se parecem hoje, mudam por razões
diferentes) e cria uma abstração cheia de parâmetros para agradar três chamadores.

**SOLID, onde cabe.** Responsabilidade única e inversão de dependência pesam muito aqui: `ChatClient` é um
`Protocol`, `llm/` não conhece `engine/`, `rules/` não conhece quem a usa. Aberto/fechado vale para pontos de
extensão reais (pacote de narração, sistema de regras como dado). Liskov e segregação de interfaces quase não
aparecem num código de funções puras e dataclasses: **não invente hierarquias** só para satisfazê-los.

**Separation of Concerns.** O motor decide, o CLI orquestra, a narração apresenta, o LLM propõe.
*Atrapalha* quando vira camada que só repassa chamada, sem responsabilidade própria.

**Composição sobre herança.** Prefira funções, dataclasses e `Protocol`. Herança só para especializar exceção
ou modelo Pydantic (`StrictModel`). Se a herança rasa for claramente mais simples, ela está permitida.

**Alta coesão e baixo acoplamento; encapsulamento; responsabilidade única.** Um módulo muda por um motivo.
O que é interno leva `_` e fica fora do `__init__.py`; a API pública de um pacote é o que o `__init__` exporta.
Coesão é sobre *motivo de mudança*, não sobre tamanho: fragmentar em muitos módulos minúsculos pode piorar
a leitura.

**Legibilidade, previsibilidade, simplicidade.** Código é lido mais vezes do que escrito. Mesma entrada, mesma
saída; sem efeito escondido; nomes que dispensam comentário. Comentário explica o *porquê*.

## Parte B. Decisões arquiteturais do Devaneio (mudam só com o dono)

| Decisão | Onde vive | O que a quebraria |
|---|---|---|
| Motor de regras só no backend e puro | `backend/src/devaneio/engine/` | lógica de jogo no frontend; ação do motor que muta a entrada ou faz I/O |
| Estado é JSON puro, em turnos, fonte única da verdade | `schema/game_state.py`, arquivo de partida do CLI | estado derivado gravado, estado em memória que diverge do arquivo |
| Regras são dados declarativos, nunca código | `rules/` (expressões como `2d6 + FOR`) | `eval`, plugin executável, fórmula Python |
| LLM é opcional e só propõe | `llm/`, `cli/freeform.py` | LLM aplicando mudança direta de estado; jogo que deixa de funcionar sem LLM |
| Contrato único gerado do Pydantic | `contract/`, `frontend/src/contract/` | tipo TS escrito à mão; JSON Schema editado à mão |
| Aleatoriedade reprodutível (SplitMix64 próprio) | `rng.py` | `random`, `time`, `uuid` dentro do motor |
| Narração é camada de exibição | `narration/`, `llm/narration.py` | prosa gravada no estado; narração consumindo `rng_draws` |
| Tensão é derivada e só observada | `engine/director.py` | usá-la para decidir ritmo sem o dono pedir |

Leia também o [README](../../README.md) (princípios e etapas) antes de propor mudança que cruze essas linhas.
