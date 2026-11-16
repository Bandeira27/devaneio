# Sistema de regras

Como um sistema de regras é descrito (em dados, nunca em código), como o autor cria o seu e como verificar.

Um sistema é um arquivo JSON (`contract/rules.schema.json`) com atributos, dificuldades,
habilidades, armas, modificadores e graus de resultado. Fórmulas são expressões de dados
interpretadas pelo motor, nunca código:

```
expr   := term (("+" | "-") term)*
term   := factor ("*" factor)*
factor := INT | DICE | IDENT | "(" expr ")" | "-" factor
DICE   := INT? "d" INT          (2d6, d20)
IDENT  := [A-Z][A-Z0-9_]*       (id de atributo)
```

O sistema padrão, **Devaneio Básico** (`backend/src/devaneio/rules/data/default.json`):
atributos FOR, AGI, MEN e PRE de 1 a 5; teste `2d6 + atributo` contra uma dificuldade
(Fácil 7, Normal 9, Difícil 11, Heroica 13); margem ≤ -5 é falha crítica, ≥ 5 sucesso
crítico; vantagem/desvantagem ±2; `max_hp = 6 + FOR * 2`.
Personagem com hp 0 está fora de combate e **não age** (`testar`, `atacar` e `ir` com `id:`) até ser curado; o sistema
pode mudar isso com `combat.fallen_can_act: true`.

## Sistema e narração do autor

A campanha pede `rules_id` e `narration_id` (padrões `default` e `pt-br`). O id é procurado em `sistemas/` e
`narracoes/` ao lado do arquivo da campanha e, se não houver, entre os embutidos. Um arquivo pode declarar só o que
muda com `"extends"` (um nível): listas mesclam por `id`, blocos campo a campo, e o resultado é validado como um
sistema completo (`contract/rules_extension.schema.json`, `contract/narration_extension.schema.json`). Formato,
regras da mescla e limites em [`desenho-sistemas-do-usuario.md`](desenho-sistemas-do-usuario.md).

```bash
cd backend
.venv/bin/python -m devaneio.cli verificar ../campaigns/minha-campanha.json
```

`verificar` confere campanha, sistema e narração e imprime `erro:` (sai com 1) ou `aviso:` em português: habilidade
de `check_passed` que o sistema não tem, gatilho por queda de NPC sem prender o local, regra de narração que nunca
dispara. Uma partida salva guarda o hash do sistema e da narração; se eles mudarem, ela avisa ao abrir (e segue).

A aleatoriedade é reprodutível: o estado guarda só `rng_seed` e `rng_draws`, e o gerador
(SplitMix64 próprio) é recriado a partir deles a cada ação.
