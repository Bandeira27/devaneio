# 05. Segurança e fronteira do LLM

O LLM é **entrada não confiável**. O que ele devolve é um palpite a validar, nunca uma ordem.

## Regras

1. **O LLM só propõe.** A proposta (`Proposal`, até 3 ações) tem allow-list: `check`, `attack`, `move`, `rest`.
   Dano e cura arbitrários e mudanças diretas de marcos ficam **fora**. Não ampliar a allow-list sem o dono.
2. **Toda proposta vira comando do CLI** e passa por `execute()`, reaproveitando as validações do motor.
   Tudo ou nada: se uma ação falha, nada é aplicado. O modelo nunca rola dados nem decide dano.
3. **Ids são slugs validados**, então uma proposta não consegue injetar outro comando nem escapar do formato.
   Qualquer texto do modelo que vire argumento passa por validação antes de montar a linha de comando.
4. **Saída do LLM é lenienete na leitura, estrita na aplicação**: modelos de proposta usam `extra="ignore"`;
   o que chega ao motor é validado de novo por modelos estritos.
5. **A prosa do LLM é só exibição** e nunca volta ao estado. Se o modelo falhar, cai na gramática e avisa.
6. **Nunca executar código vindo de dado**: sem `eval`, `exec`, `compile`, `pickle`, `yaml.load`, `subprocess`
   com entrada externa, import dinâmico por nome externo. Regras do jogo são dados interpretados.
7. **Todo JSON externo** (campanha, partida, regras, resposta do LLM) entra por modelo Pydantic.
8. **Segredos** (`DEVANEIO_LLM_API_KEY`) só por variável de ambiente; nunca em log, mensagem de erro, partida,
   campanha, fixture, commit ou saída do CLI. A chave só viaja no cabeçalho da requisição.
9. **Rede**: só `http(s)` com host, validado em `LlmConfig` antes de qualquer requisição. Chamadas
   `urllib` levam `# noqa: S310` com essa justificativa, e **só** lá. Timeout sempre definido.
10. **Caminhos de arquivo vindos de dado não são confiáveis.** `SaveFile.campaign_path` é relativo ao arquivo da
    partida, mas `load_game` hoje o resolve **sem restringir `..`**: um arquivo de partida adulterado pode
    apontar para outro JSON local (e a mensagem de validação pode citar trechos dele). Risco baixo num CLI
    local, mas conhecido: ao mexer nisso, restrinja ou avise, e não reproduza o padrão em código novo.
11. **Privacidade**: com LLM ligado, o contexto da partida (inclusive segredos de NPCs presentes) vai ao servidor
    configurado, e o CLI avisa na abertura. Não aumentar o contexto enviado sem atualizar esse aviso e o README.

## Checklist ao mexer em `llm/`, `cli/` ou carga de arquivos

- O que o modelo pode fazer mudou? Atualize a allow-list *e* o teste que a prova.
- Há caminho novo de texto externo até o motor, o shell, um arquivo ou um log?
- Há segredo que possa aparecer em exceção, `repr` ou mensagem de erro?
- O teste usa o servidor falso, não rede real?
