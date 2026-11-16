# Desenho: sistemas de regras e narrações do usuário

Segundo passo do [rumo de extensibilidade](rumo-extensibilidade.md). Hoje só os sistemas e pacotes embutidos
carregam (`load_builtin_rules`, `load_builtin_pack`), a narração é fixa em `pt-br` e nada confere a campanha contra
o conteúdo do autor. Este passo abre a carga de arquivo, com `extends`, e um validador de autoria em português.

## Formato dos arquivos

Tudo é **JSON**, o mesmo formato da campanha, com JSON Schema em `contract/`. Nada de código.

```
campaigns/
  minha-campanha.json            campanha (ganha "narration_id")
  sistemas/meu-sistema.json      sistema de regras do usuário
  narracoes/meu-estilo.json      pacote de narração do usuário
```

A campanha cita `"rules_id": "meu-sistema"` e `"narration_id": "meu-estilo"` (só ids, sem caminho; os padrões são
`default` e `pt-br`). O id é procurado primeiro em `sistemas/` ou `narracoes/` ao lado da campanha, depois nos
embutidos. O catálogo do servidor continua lendo só os `*.json` da raiz das campanhas.

### Sistema com `extends`

Só o que muda; o resto vem do pai (`default`):

```json
{
  "id": "meu-sistema",
  "extends": "default",
  "name": "Meu Sistema",
  "skills": [
    {
      "id": "magia",
      "name": "Magia",
      "formula": "2d6 + MEN",
      "description": "Conjurar."
    },
    { "id": "lutar", "name": "Lutar", "formula": "2d6 + FOR + 1" }
  ],
  "weapons": [{ "id": "varinha", "damage": "1d6 + MEN", "skill": "magia" }],
  "combat": { "default_weapon": "varinha" }
}
```

`magia` e `varinha` são acrescentados, `lutar` substitui o do pai e `combat` muda só `default_weapon`. Sem
`extends`, o arquivo é um sistema completo, como o `default.json`.

Regras da mescla (um nível, sem cadeia):

- listas `attributes`, `difficulties`, `skills`, `weapons`, `modifiers`: por `id`, na ordem do pai; o filho
  substitui o item de mesmo id ou acrescenta no fim;
- blocos `outcomes`, `combat`, `dispositions`, `rest`: campo a campo;
- escalares (`name`, `description`, `max_hp`): o filho vence;
- `id` obrigatório e diferente do pai;
- o pai é embutido ou um arquivo **sem** `extends`; senão é erro ("só um nível").

Depois da mescla o resultado passa pela validação de sempre (`RuleSystem` e `validate_rules`).

### Pacote de narração com `extends`

```json
{
  "id": "meu-estilo",
  "extends": "pt-br",
  "rules": {
    "move": ["Vocês seguem para #destino#."],
    "reveal": ["O segredo cai no chão: #fato#"]
  }
}
```

Cada chave é um tipo de evento (`check`, `move`, `reveal`...), com variante opcional (`check.success`). O filho
substitui as chaves iguais e herda o resto; `language` é herdada se omitida. As variáveis `#x#` valem as do tipo
de evento.

### Contrato

`RuleSystemExtension` e `NarrationPackExtension` (todos os campos opcionais, exceto `id`) saem em
`contract/rules_extension.schema.json` e `contract/narration_extension.schema.json`, com tipos TS, para editor e
autores técnicos. Os modelos completos `RuleSystem` e `NarrationPack` não mudam: o arquivo já mesclado não tem
`extends`.

## Carga

`game/content.py` orquestra; `cli` e `server` só fazem I/O. Para cada id:

- o id é um slug, então não há `..`; o arquivo resolvido precisa ficar dentro da pasta da campanha (também contra
  symlink);
- limite de tamanho por arquivo, checado antes de ler;
- o `id` dentro do arquivo precisa casar com o nome do arquivo e com o `rules_id` / `narration_id` da campanha;
- todo erro vira `GameError` em português, citando o arquivo e sem caminho absoluto.

## Validador de autoria

`check_content(campaign, rules, pack)` devolve achados `erro` ou `aviso`, em português:

- erro: `check_passed` com `skill_id` que o sistema não tem (pendência do passo 1);
- aviso: marco ou fato que revela por `npc_down` de um NPC que começa fora do local do grupo, sem `at_location`
  (o evento vazaria o nome de quem o grupo não vê);
- aviso: pacote de narração com chave de tipo de evento desconhecido (`chek.success`) ou variante que o narrador
  não usa (`check.sucesso`), tipo de evento do motor sem regra, e regra auxiliar que nenhuma raiz alcança.

`python -m devaneio.cli verificar <campanha>` imprime os achados e sai com 1 se houver erro. O servidor roda só os
erros na subida, para uma campanha com sistema ruim não falhar apenas ao criar a mesa.

## Partidas salvas

O `SaveFile` ganha `content` opcional com o hash do sistema de regras e do pacote de narração já mesclados. Ao
abrir, se algum mudou, a sessão traz um aviso em português dizendo qual. Não recusa e não migra: o conteúdo muda
de propósito durante a autoria. Salvos antigos, sem `content`, abrem sem aviso.

## Ordem dos commits

1. Este documento.
2. `extends` de regras e contrato.
3. `extends` de narração e `Campaign.narration_id`.
4. Carga de pastas (`game/content.py`), erros tratados no CLI e no servidor, catálogo conferindo regras.
5. Validador de autoria e comando `verificar`.
6. Hash do conteúdo e avisos.
7. Documentação (`docs/sistema-de-regras.md`) e regra 05.

## Fora desta etapa

Cadeia de `extends`, editor, ações declarativas definidas pelo autor, versionamento do conteúdo com migração.
