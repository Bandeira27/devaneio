---
name: review-ui
description: Use ao revisar ou concluir uma mudança de interface do app Angular (tela, componente, estilo, movimento): o checklist de aceitação de fluxo, estados, acessibilidade, tokens, movimento e responsivo, com a matriz de telas e larguras.
---

# Revisar uma mudança de UI

Aplica as rules [11](../../rules/11-design-system.md) e [12](../../rules/12-movimento.md) e os padrões de
[`docs/padroes-de-interacao.md`](../../../docs/padroes-de-interacao.md). O papel `ui-reviewer` usa esta lista; quem
escreve a mudança também deve passar por ela antes de pedir revisão.

## Antes de olhar

`scripts/check` completo verde. Ele já barra valor fora de token, contraste, token sem uso, story faltando e build.

## Checklist

**Fluxo**

- [ ] O caso comum cabe em poucos toques (ação frequente: no máximo 3).
- [ ] Ação que gasta a vez ou não se desfaz pede confirmação **dentro** do fluxo, ou oferece desfazer.
- [ ] Rótulos iguais em todo lugar (botão = título da folha); verbo no imperativo.
- [ ] Todo erro diz o que aconteceu e o que fazer; texto humano, sem id nem código.
- [ ] Nenhum beco sem saída: erro e vazio têm ação (tentar de novo, voltar, criar).
- [ ] **Caminho com passos** (entrada na mesa): todo passo prometido tem uma tela que o mostra como atual, e toda tela do caminho mostra os passos; o nome do passo diz onde a pessoa está.
- [ ] **Os passos moram num lugar só**: no topo da coluna de contexto do palco `.dv-stage`, à esquerda, acima do título e fora de cartões, em todas as telas e larguras. Tela nova do caminho usa o palco; não há tela que os centralize ou os ponha dentro de um card. Página de lista ou de gerenciamento nunca hospeda um passo: ela aponta para a tela do passo, que fica fora do quadro de gerenciamento (sem barra lateral nem item de menu marcado).
- [ ] **Toda tela do caminho tem saída, no mesmo lugar**: um botão discreto abaixo da ação principal (anfitrião: "Voltar às mesas"; convidado: "Voltar ao início"), também no celular e depois do botão principal. Os passos não são clicáveis: o passo anterior pode já ter criado algo que não se refaz.
- [ ] **Pré-requisito obrigatório é conduzido, não oferecido**: o sistema leva ao passo que falta; botão só serve para voltar a ele. Exceção, só se declarada (o anfitrião sem personagem).
- [ ] O caminho foi percorrido **de ponta a ponta nos dois papéis** (anfitrião e convidado), incluindo reentrada com e sem o pré-requisito e o botão Voltar; mudou o destino de uma ação, conferiu quem mais aponta para a tela antiga (rotas, textos, docs).

**Estados** (os que fizerem sentido)

- [ ] Vazio de lista **explica** o que a coisa é e leva à ação (a lista de mesas sem mesa não é só um título e um botão). Carregando, vazio, erro, em envio (rótulo mantido, botão não clicável), bloqueado **com motivo ligado** (`aria-describedby`), sem conexão.

**Acessibilidade**

- [ ] Um `h1` por tela; landmarks; ordem do HTML = ordem visual e de foco.
- [ ] Foco devolvido quando o elemento focado some (fechar folha, trocar de etapa, dispensar aviso, desfazer).
- [ ] Nome acessível em todo controle; ícone sozinho tem `aria-label`.
- [ ] Informação nunca só por cor; alvo de toque ≥ 44 px nos controles principais.
- [ ] Região viva não anuncia a carga inicial nem repete o mesmo texto.
- [ ] Teclado: tudo alcançável, Esc fecha o que é modal, setas nos grupos de escolha.

**Tokens e movimento**

- [ ] Nenhum valor literal de cor, duração, curva, sombra, `z-index`.
- [ ] Cada movimento responde a uma das 5 perguntas da rule 12 (diga qual na descrição do PR); só `opacity`, `transform`, cor.
- [ ] Com `prefers-reduced-motion` o estado final vale na hora e nada desliza.

**Composição e hierarquia**

- [ ] Tela larga: a informação ocupa o espaço em painéis lado a lado (contexto | tarefa; cena | história | ficha), não numa coluna de celular esticada; o cabeçalho e o conteúdo se alinham ao mesmo contêiner.
- [ ] O que é primário tem peso (ação do turno, "Continuar", o link do convite); o apoio e o técnico ficam recolhidos ou discretos.
- [ ] Rosa só em ação e seleção; quem fala em tinta; hierarquia por escala, caixa e superfície (as fontes só têm peso 400).

**Transição**

- [ ] Trocar de tela não mostra tela errada nem salto de layout; espera longa mostra a folha de transição e nunca bloqueia o toque.

**Matriz visual** (navegador embutido ou `npm run storybook`, com o painel visível)

- [ ] 375×812, 768×1024, 1300×800 e 1440+ (três painéis da mesa); sem rolagem horizontal em 320 px; texto a 200 % sem perda.
- [ ] Telas: mesa (feed longo, ação pendente, bloqueada, sem personagem, desconectada, partida encerrada), home (com e sem mesas), criar mesa, sala de espera (como anfitrião e como convidado), convite, entrar, personagem, as folhas.

## Armadilhas de verificação

- O painel do navegador escondido trava view transitions e navegação: mostre-o antes.
- O servidor guarda a lista de arquivos do build: depois de `ng build`, reinicie `python -m devaneio.server`.
- jsdom não anima, não rola e não tem `matchMedia`: prove classe, atributo e foco; o resto, no navegador.
