# Fatos e revelações

Como um segredo vira fato e quando o motor o revela. O desenho completo está em [`desenho-visibilidade-revelacoes.md`](desenho-visibilidade-revelacoes.md).

O que o autor quer esconder vai em `Campaign.facts` (`id`, `text`, `about`, `reveal_when`) e em `private_notes`
(local, facção, NPC e marco). `private_notes` nunca é público. Um fato começa oculto e **o motor decide quando ele se
torna público**: quando todas as condições de `reveal_when` valem (checado ao fim do turno pelo diretor e depois de
cada comando), ou quando o anfitrião usa `revelar <id>` (a única via de um fato sem condições). O estado guarda só
`revealed_facts` (id → turno); o texto vive na campanha. `fatos` (anfitrião) lista todos; `olhar` mostra o que o grupo
já sabe. O LLM sempre recebe os fatos revelados (`fatos_revelados`); os ocultos e as notas só com `include_private` e só os que dizem respeito ao que está em cena (NPCs presentes, o local, marcos ativos ou sem `about`)
(solo, ou `--segredos-no-llm` na mesa). Desenho em [`desenho-visibilidade-revelacoes.md`](desenho-visibilidade-revelacoes.md).
