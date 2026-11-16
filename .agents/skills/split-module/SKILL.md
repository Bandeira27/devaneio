---
name: split-module
description: Use ao dividir um módulo ou arquivo que mistura responsabilidades (Python ou TypeScript) em partes coesas, sem mudar comportamento nem a API pública, e ao revisar se uma divisão proposta vale a pena.
---

# Dividir um módulo

Aplica a [rule 09](../../rules/09-responsabilidades.md). Divisão é só mover código: nenhum comportamento muda.

## Passos

1. **Diagnostique.** Escreva uma frase por responsabilidade que o arquivo cumpre hoje. Se houver uma só, **pare**: não
   há o que dividir. Se a divisão só espalharia o que se lê junto, também pare e diga por quê.
2. **Levante quem usa.** Procure todos os imports do arquivo, em código e testes (`grep` do caminho do módulo e dos
   símbolos). Isso define a API pública que precisa continuar de pé.
3. **Desenhe as partes e as dependências.** Um arquivo por responsabilidade, nomes que dizem o assunto (nada de
   `utils`; em Python, nada que sombreie a biblioteca padrão). Desenhe as setas de import entre as partes: **sem
   ciclo**. Se houver ciclo, junte as duas partes ou extraia uma terceira.
4. **Prepare a porta de entrada.**
   - Python: transforme `modulo.py` em pasta `modulo/` com `__init__.py` que reexporta o mesmo conjunto público.
   - TypeScript: o arquivo que os outros já importam continua exportando o mesmo; as partes ficam ao lado.
5. **Mova sem editar a lógica.** Copie as definições para os arquivos novos, ajuste só imports e visibilidade. Não
   renomeie símbolos públicos. Se algo precisa mudar no código, é outro commit.
6. **Rode `scripts/check`.** Camadas (import-linter e ESLint) devem continuar verdes, a contagem de testes igual, e
   `git diff contract frontend/src/contract` vazio.
7. **Atualize quem cita o caminho:** docs, skills, rules, docstrings de módulo.
8. **Um commit `refactor:` por módulo dividido**, com o motivo na mensagem (qual responsabilidade se separou).

## Armadilhas

- **Ciclo escondido num despachante:** a função que consulta a tabela de comandos e a tabela que referencia os
  handlers acabam em arquivos diferentes e se importam. Mantenha tabela e consulta juntas.
- **`__init__` que importa demais:** reexportar tudo carrega tudo. Ferramentas de build que só precisam dos modelos
  não podem puxar o servidor HTTP por um `__init__` pesado.
- **Teste que importa símbolo privado** (`_Parser`, `_tokenize`): ao mover, o caminho muda. Reexporte ou ajuste o
  import do teste, sem mudar o que ele verifica.
- **Em Angular, service que injeta service** cria ciclo de injeção: passe a dependência por parâmetro (função ou
  construtor) em vez de importar o store de volta.
- **Contrato Pydantic:** o título do esquema vem do nome da classe, não do módulo; mover a classe de arquivo não deve
  alterar `contract/`. Se alterou, algo foi renomeado sem querer.
- **Dividir arquivo de teste:** divida por assunto, nunca apague caso; confira que a contagem de testes não caiu.
