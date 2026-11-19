# Devaneio

Uma mesa de RPG onde quem narra é uma IA. Você joga sozinho, no terminal, ou chama os amigos para uma mesa
por turnos, cada um no seu celular ou computador.

O nome vem daquela sensação de uma memória meio desbotada, que você não tem certeza de que viveu. A aparência do
jogo tenta ser isso: o que acabou de acontecer fica nítido e o resto vai esmaecendo.

## O que você precisa saber antes

Algumas ideias guiam o projeto, e explicam por que ele é como é:

- **As regras do jogo ficam no motor, não na IA.** Dados, dano e acertos são sempre resolvidos pelo motor de regras.
  A IA conta a história e sugere o que fazer, mas quem decide o que vale é o motor.
- **A IA é opcional.** Sem ela o jogo funciona inteiro, com a narração feita por gramáticas. Com ela, o texto fica mais
  solto. Você usa o seu próprio modelo e a sua própria chave, e nada passa por um servidor nosso.
- **Regras são dados.** Um sistema de regras é um arquivo que descreve fórmulas, não um código que alguém roda.
  Assim dá para criar o seu sem risco para o computador de ninguém.
- **Uma partida é um arquivo.** O estado do jogo é um JSON simples, salvo a cada ação.

Para onde o projeto está indo (campanhas e sistemas criados por qualquer pessoa) está em
[`docs/rumo-extensibilidade.md`](docs/rumo-extensibilidade.md).

## Jogar sozinho, no terminal

Você precisa de Python 3.10 ou mais novo e do [uv](https://docs.astral.sh/uv/).

```bash
cd backend
uv venv && uv pip install -e ".[dev]"
.venv/bin/devaneio-terminal nova ../campaigns/sombra-do-vale.json partida.json
.venv/bin/devaneio-terminal jogar partida.json
```

Dentro do jogo, digite `ajuda` para ver os comandos. Os mais usados: `olhar`, `entrar <id> "<nome>"`,
`ir <local>`, `testar <habilidade> <dificuldade>`, `atacar <arma> <alvo>`, `ficha`, `fim` e `sair`.

## Criar e gerenciar suas campanhas

Quem hospeda cria e edita campanhas no próprio navegador, sem mexer em JSON. Você precisa de [uv](https://docs.astral.sh/uv/)
e de Node 24.15 ou mais novo. Na pasta do projeto, um comando só:

```bash
./devaneio
```

Na primeira vez ele prepara o backend e constrói o app (demora um pouco); depois sobe direto. Ele repassa as opções ao
servidor (`./devaneio --help` lista todas).

O navegador abre em `http://localhost:8765`, na lista de campanhas. O card **Nova campanha** abre o editor: locais, NPCs,
facções, marcos e fatos, com os erros em português, avisos de autoria e uma prévia do que o jogador e a IA veem.
Campanha que já tem mesa não é sobrescrita: o editor lista as mesas que a travam (as do servidor, de qualquer navegador desta máquina) e oferece encerrá-las, assumir o lugar de anfitrião ou salvar uma cópia.

O editor só atende **o computador que roda o servidor**, aberto por `localhost`. Os amigos que entram pela rede nunca o
veem, e abrir pelo endereço da rede (`192.168.x.x`) também não o libera. Se você expõe o servidor por proxy ou túnel,
suba com `--sem-editor`: a guarda não os cobre. Quer desligá-lo? Use `--sem-editor`. O desenho está em [`docs/desenho-editor.md`](docs/desenho-editor.md).

## Jogar com os amigos

Quem hospeda roda o servidor e manda um link; os outros entram pelo navegador, sem instalar nada. O comando é o mesmo
da seção anterior; se preferir escolher as pastas, use `--campanhas`, `--dados` e `--web`. Com o ambiente já
instalado, `devaneio` (em `backend/.venv/bin`) faz o mesmo que `./devaneio`, sem preparar nada.

Crie a mesa, escolha a campanha e copie o link do convite. Para os amigos entrarem pela mesma rede, suba com
`./devaneio --host 0.0.0.0` e troque `localhost` no link pelo endereço do seu computador na rede (algo como `192.168.0.5:8765`).
Você segue abrindo o seu navegador por `localhost` para editar. A mesa roda em HTTP simples, então é para rede de casa,
não para a internet.

A API que o app usa está em [`docs/api-http.md`](docs/api-http.md).

## Com a IA narrando

Aponte para qualquer servidor que fale o formato OpenAI (Ollama, por exemplo) antes de subir o jogo:

```bash
export DEVANEIO_LLM_BASE_URL=http://localhost:11434/v1
export DEVANEIO_LLM_MODEL=nome-do-modelo
```

Com isso você pode digitar o que quer fazer em linguagem natural ("tento convencer o ferreiro") e a IA narra o que
acontece. O texto da partida vai para o servidor que você configurou, e o jogo avisa disso na entrada. Quer
desligar? Use `--sem-llm`. Mais detalhes, incluindo a chave e o que a IA nunca pode fazer, em [`docs/llm.md`](docs/llm.md).

## Como o projeto está organizado

```
backend/    Python: regras, motor, orquestração do jogo, linha de comando e servidor da mesa
frontend/   TypeScript: os tipos gerados do contrato e o app Angular do jogador (frontend/app/)
contract/   O contrato entre as duas pontas, gerado a partir dos modelos do backend
campaigns/  Campanhas de exemplo
docs/       Documentação por assunto
```

## Mexendo no código

```bash
git config core.hooksPath .githooks   # uma vez
scripts/check --fast                  # conferência rápida (a que roda antes de cada commit)
scripts/check                         # conferência completa: testes, tipos, contrato
```

Para mexer só no backend: `cd backend && .venv/bin/pytest -q`, e `python -m devaneio.export_schema` regenera o contrato.
Para o app em desenvolvimento: `cd frontend/app && npm start` (abre com proxy para o servidor na porta 8765).

`scripts/check` é a única definição de "pronto": os hooks e o CI chamam o mesmo script. As instruções para quem
contribui, pessoa ou IA, estão em [`AGENTS.md`](AGENTS.md).

## Para ler com calma

| Quero saber...                                  | Leia                                                     |
| ----------------------------------------------- | -------------------------------------------------------- |
| o mapa da documentação                          | [`docs/index.md`](docs/index.md)                         |
| como criar um sistema de regras ou uma narração | [`docs/sistema-de-regras.md`](docs/sistema-de-regras.md) |
| como o motor e o diretor funcionam              | [`docs/motor.md`](docs/motor.md)                         |
| o que já foi construído                         | [`docs/historico.md`](docs/historico.md)                 |
