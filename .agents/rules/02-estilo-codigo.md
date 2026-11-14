# 02. Estilo e código limpo

O que `ruff`, `ruff format` e `mypy --strict` já cobrem **não é repetido aqui**: está em
`backend/pyproject.toml`. Este arquivo trata do que só julgamento resolve.

## Linguagem e nomes

- Documentação, comentários, docstrings, mensagens de erro e commits em **pt-br**; identificadores em inglês
  (`deal_damage`, `rng_draws`). Ids de domínio são slugs (`aria`, `vila`).
- Nome diz o quê, não o como. Evite abreviações opacas (`l`, `x`); se o nome precisa de comentário, troque o nome.
- Comentário explica o *porquê* (restrição, decisão, armadilha), nunca o que a linha faz.
- Compatível com **Python 3.10** (declarado em `requires-python`; o CI roda 3.10 e 3.12). Use
  `from __future__ import annotations` e tipos completos.

## Estrutura

- Resultado de ação é `@dataclass(frozen=True)`. Parâmetros keyword-only (`*,`) a partir de ~3 argumentos.
- Um erro de domínio por pacote (`EngineError`, `LlmError`, `ExpressionError`), mensagem em pt-br, e
  `raise NovoErro(...) from exc` ao traduzir outro.
- Reuso: antes de escrever, procure a função existente (`engine/lookup.py`, `engine/errors.py`,
  `game/commands.py`). Siga o padrão do vizinho; não crie um segundo mecanismo para a mesma coisa.
- Documentação de módulo curta (primeira linha: o que o módulo é; depois, só o que não é óbvio).

## Tamanho e complexidade são indicadores, não limites

Sinais para **olhar com atenção**: função acima de ~40-60 linhas, mais de ~4 níveis de indentação, ramificação
excessiva, módulo acima de ~400 linhas ou com mais de um motivo de mudança, assinatura com muitos parâmetros.
Nenhum deles é regra: não há portão automático para isso (`PLR0912/0915` ficam fora do `scripts/check`).

Ao cruzar um sinal, **primeiro avalie se há problema real** de coesão ou legibilidade. Um despachante de
comandos, uma tabela ou uma sequência linear coesa pode ser longa e estar certa (`game/commands.py`, 366 linhas,
é um caso a avaliar, não a dividir por reflexo). Só proponha refatorar se conseguir dizer **qual responsabilidade
se mistura** ou **o que fica difícil de ler ou testar**. Dividir apenas para mover linhas de arquivo é proibido
como objetivo. Refatoração motivada por indicador vira commit próprio, separado de mudança de comportamento.

## Tratamento de exceções

Capture o mais estreito possível, e só o que você sabe tratar. `except:` e `BaseException` nunca (engolem
`KeyboardInterrupt`/`SystemExit`).

`except Exception` **é permitido somente em fronteira de execução**, e só com todos os critérios:

1. É uma fronteira real em que a falha vira um desfecho definido: o laço principal do CLI que mostra o erro sem
   derrubar a partida; a chamada ao LLM que vira `LlmError` e cai na gramática; um futuro handler de requisição.
2. **Nunca** em `schema/`, `rules/` ou `engine/`: o núcleo levanta erros de domínio, não os engole.
3. Preserva a causa: `raise Domínio(...) from exc`, ou registra com traceback. Nunca engole em silêncio
   (`pass`, `continue` mudo, valor neutro sem avisar o usuário).
4. Um comentário na linha diz qual é a fronteira e qual o desfecho.
5. Há teste cobrindo o caminho de falha.

Ruff `BLE001`, `S110` e `SIM105` ficam ligados. O uso legítimo leva a supressão local justificada da
[rule 07](07-qualidade-e-supressoes.md), por exemplo `# noqa: BLE001 — fronteira do laço do CLI: mostra e segue`.
Hoje o código não tem nenhum `except Exception`; se surgir, é porque há uma fronteira nova.
