# 09. Responsabilidades por módulo

Vale para Python e TypeScript. Complementa o [03](03-arquitetura.md) (quem pode importar quem): aqui o assunto é
**o que cabe dentro de um arquivo**.

## O critério: um motivo para mudar

Um arquivo tem uma responsabilidade quando só há um tipo de mudança que o obriga a ser editado. Linhas são só um
sinal para olhar com atenção, nunca o critério: um despachante com uma tabela longa e coesa está certo, e um arquivo de
150 linhas que mistura leitura, validação e persistência está errado.

Pergunta prática: **descreva o arquivo em uma frase sem usar "e"**. Se não der, provavelmente são duas coisas.

Sinais de mistura:

- **Etapas de um pipeline no mesmo arquivo.** Tokenizador, árvore, parser e avaliador de uma expressão são quatro
  motivos diferentes para mudar (`rules/expression/` é o exemplo seguido).
- **Estado, carga e ações juntos.** Uma classe que guarda sinais, busca na rede, repete requisições e ainda monta
  textos para a tela (`TableStore` antes da divisão).
- **Lógica pura presa a um framework.** Regra de negócio dentro de um `computed` ou de um método de componente só se
  testa montando a aplicação. Extraia a função pura; o framework apenas a envolve.
- **Nome que mente.** `commands` exportando validação de nome; `models` com requisições, respostas e envelope do
  contrato. Se o nome do arquivo não prevê o que há dentro, a divisão está atrasada.
- **Fronteira de segurança misturada com o resto.** Validação do que vem de fora (armazenamento do navegador, corpo
  de requisição) merece arquivo e teste próprios.

## Quando dividir e quando não

Divida quando conseguir dizer **qual responsabilidade se mistura** e **o que fica difícil de ler ou de testar** por
causa disso. Não divida quando:

- o módulo é pequeno e coeso, e as partes só fazem sentido lidas juntas (um tipo e a função que o constrói);
- a divisão só espalharia o que se lê junto, obrigando a abrir cinco arquivos para entender uma frase;
- o ganho é só mover linhas de um arquivo para outro.

Se o arquivo cresce porque a **tabela** cresce (rotas, comandos, regras de dados), isso não é mistura.

## Como dividir

1. **Nomeie as responsabilidades** antes de mexer, uma frase cada. Cada uma vira um arquivo.
2. **Desenhe as dependências entre as partes** e garanta que não há ciclo. Se duas partes se precisam, ou são uma só
   ou falta uma terceira. Ordem típica: erros e tipos, depois a lógica que os usa, por último o ponto de entrada.
3. **Mantenha a porta de entrada.** Em Python, o `__init__.py` do pacote reexporta o mesmo conjunto público; em
   TypeScript, o arquivo que os outros já importam continua exportando o que exportava. Quem usa não muda.
4. **Mova sem editar a lógica.** Divisão é um commit `refactor:` à parte, sem mudança de comportamento. Os testes
   existentes passam sem alteração (salvo o caminho de um import interno).
5. **Respeite as camadas.** A divisão fica dentro da camada de origem ([03](03-arquitetura.md); no front, as camadas do
   ESLint). Nada de arquivo novo que abra um import proibido.
6. **Atualize quem cita o caminho:** docs, skills, comentários.

A skill `split-module` leva por esses passos.

## Detalhes por linguagem

|                  | Python                                                                              | TypeScript (app Angular)                                                |
| ---------------- | ----------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| Unidade          | pacote (pasta com `__init__.py`) no lugar do módulo                                 | arquivos irmãos por assunto na mesma pasta                              |
| Porta de entrada | `__init__.py` reexporta                                                             | o arquivo de sempre (por exemplo o store) vira fachada fina             |
| Lógica pura      | funções em módulo próprio, sem I/O                                                  | funções em arquivo `.ts` sem Angular, que o store envolve em `computed` |
| Nome             | não sombreie a biblioteca padrão (`nodes.py`, não `ast.py`)                         | o nome do arquivo diz o assunto (`names.ts`, não `utils.ts`)            |
| Cuidado          | `__init__` pesado carrega tudo ao importar; o servidor não pode importar `http` ali | um service que importa outro service cria ciclo de injeção              |

## Duplicação

Conhecimento repetido em duas ou mais cópias (a mesma validação, o mesmo retry, o mesmo cabeçalho de tela) sobe para a
camada mais baixa que todos os usuários já enxergam. Duas cópias são aviso, três são motivo para extrair. Mas só
extraia o que é **o mesmo conhecimento**: duas funções parecidas que mudam por razões diferentes devem continuar duas.
