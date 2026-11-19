# Padrões de interação

Como o app do jogador se comporta, para que telas diferentes se sintam iguais. O visual está em
[`design-system.md`](design-system.md) e o movimento em [`movimento.md`](movimento.md). Quem revisa usa a skill
[`review-ui`](../.agents/skills/review-ui/SKILL.md).

## Caminho de entrada

Criar uma mesa ou entrar por convite é um caminho curto de três passos: **Mesa** ou **Convite**, **Personagem** e
**Sala** (a sala de espera). Os passos ficam visíveis em **toda** tela do caminho, cada uma com o seu como atual (as
constantes estão em `shared/game/entry-steps.ts`); ao começar a campanha, a mesa deixa de ser entrada e os passos somem.
O caminho **conduz**: criar a mesa ou aceitar o convite leva direto ao personagem, e quem foi convidado e chega à sala
sem personagem é levado de volta a ele. O personagem não é um botão a descobrir. **Toda tela do caminho tem saída**, no mesmo lugar: um botão discreto abaixo da ação principal. O anfitrião volta às mesas da campanha, e quem foi convidado volta ao início; a mesa fica guardada e reaparece em "Continuar". Os passos não são clicáveis, porque o passo anterior pode já ter criado a mesa ou a entrada. O primeiro passo tem tela própria, em tela cheia como as outras do caminho (fora do quadro com a barra lateral da campanha, para não parecer parte de "Mesas"): páginas de lista (as mesas da campanha) só apontam para ele com um botão, sem formulário nem passos embutidos. Só o anfitrião pode seguir sem
personagem ("Ir para a mesa sem personagem"); para ele, "Criar personagem" fica na sala como retorno. Quem já tem
personagem vai direto à sala, com o passo Personagem como feito. A tela larga mostra o contexto ao lado da tarefa; o celular mostra o mais provável primeiro (a tarefa; na home, "Continuar"). O que é técnico
(endereço do servidor, código do convite) fica em "Opções avançadas", recolhido: o centro do convite é o link e o "Copiar".

**A tela de entrar diz para onde o convite leva.** Com o convite no link, ela pergunta ao servidor o nome da mesa (o título
da campanha; só quem tem o convite o recebe) e mostra "Você foi convidado para _nome_" em qualquer largura (no celular é o que confirma que o link é o certo). A pergunta é feita uma vez ao abrir
a tela, nunca por tecla; convite recusado mostra o aviso, e falha de rede deixa o texto genérico (a entrada não é bloqueada).

## Estados de uma tela ou região

| Estado                        | O que mostrar                                                                       | Componente                         |
| ----------------------------- | ----------------------------------------------------------------------------------- | ---------------------------------- |
| Carregando                    | texto curto do que está sendo aberto; sem esqueleto piscando                        | `dv-state` `loading`               |
| Vazio                         | o que falta e o próximo passo ("Ninguém mais entrou. Convide o grupo")              | `dv-state`                         |
| Erro                          | o que houve em frase humana **e** uma saída: "Tentar de novo" ou "Voltar ao início" | `dv-state` `error`                 |
| Sem conexão                   | badge discreto no cabeçalho; ações **bloqueadas com o motivo**                      | `dv-connection-badge`, `dvBlocked` |
| Sessão vencida ou mesa sumida | aviso com saída; a sessão guardada é esquecida                                      | `dv-notice`                        |

Nenhuma tela fica sem saída: erro e vazio sempre oferecem uma ação.

## Desfecho no feed

Teste, ataque, dano e cura mostram o desfecho num **selo** que abre a nota mecânica: ícone, texto e tom (nunca só a cor), não clicável. O servidor entrega só o grau (`EventView.outcome`); o servidor tira da nota o desfecho que o selo já diz, para o leitor de tela ouvir uma vez. A cor do desfecho fica só no selo: a narração não se colore. Evento sem desfecho não tem selo.

## Composição para a tela larga

Desktop não é o celular esticado. A informação se divide em painéis lado a lado dentro do contêiner do app, e o celular
continua uma coluna. A **home** é capa e painel (a apresentação, a campanha e as mesas guardadas de um lado; criar e
convite do outro). **Entrar**, **convite** e **personagem** têm o contexto à esquerda e a tarefa à direita. A **mesa**
tem duas colunas (cena e grupo com as ações; a história) a partir de 64rem e três a partir de 90rem (cena e grupo; a
história; a ficha de quem joga com as ações). A ordem do HTML é a de leitura no celular e na tela muito larga; entre 64 e 90rem, em que a barra de ações fica visualmente
abaixo da cena, o Tab passa pela história antes das ações, e o link "Pular para as ações" cobre esse caminho.

## Hierarquia de ações

O que é do turno (Ir, Testar, Atacar, Falar) tem destaque (com mestre de IA o primário é Falar; sem ele, Testar); o que é de apoio (Ficha e, só para o anfitrião, Comando) é discreto. "Continuar" a
última mesa é o botão principal da home; criar mesa só é primário quando não há mesa guardada. As saídas da cena são
atalhos para `Ir` e passam pela mesma confirmação.

## Fim de partida

Vitória ou derrota aparece como aviso com a saída "Voltar ao início"; a história continua legível e as ações ficam bloqueadas com o motivo.

## Transição entre telas

- O cabeçalho é a âncora: fica parado e só a página "vira" (sai para a esquerda, entra da direita, um deslocamento curto).
- Se a troca demora mais de 150 ms (código ou dados), uma **folha de transição** cobre a página que estava saindo, com a
  marca e "Abrindo…"; ela nunca bloqueia o toque e some no instante em que a tela chega (a tela pronta não espera a
  folha). A região principal fica com `aria-busy` durante toda navegação e o leitor de tela ouve "Abrindo…" quando a folha
  aparece. Troca rápida nunca mostra a folha.
- As telas são pré-carregadas em segundo plano (`withPreloading`).
- **Nenhuma tela errada, nem por um instante:** quem já entrou na mesa não vê o convite do convidado; quem não é anfitrião
  não vê a tela do convite. Essas decisões são `canActivate` da rota, não redirecionamento depois de desenhar.
- O carregamento tem a forma da tela pronta (dentro do mesmo contêiner) e diz o que está abrindo ("Abrindo o seu personagem…").
- Erro que não melhora tentando de novo (mesa que sumiu, sessão vencida) oferece só **Voltar ao início**.

## Botões

- O rótulo é um verbo no imperativo e é **o mesmo** em todo lugar: o botão que abre uma folha dá o título dela
  (Ir, Testar, Atacar, Falar, Comando). "Entrar" só para convite.
- **Em envio:** `dvLoading`, rótulo mantido, clique engolido. Nunca trocar o texto por "Criando…".
- **Bloqueado por um motivo:** `dvBlocked` + `aria-describedby` apontando para o motivo visível. `disabled` nativo só
  quando o motivo é óbvio e o foco não precisa ficar.
- Um primário por tela ou folha, à direita no rodapé.

## Formulários

- Nome primeiro; `autocomplete` certo; Enter envia.
- O erro aparece **no envio**, fica junto do campo e **some ao digitar**.
- Falha do servidor vai num `dv-notice` de erro acima do botão, em frase humana.
- Valor derivado nasce preenchido e editável (o personagem nasce com o nome de quem joga).
- Campo que só importa às vezes não é pedido (o código do convite só aparece quando não veio no link).

## Edição com validação ao vivo (editor)

O servidor confere a campanha a cada edição, depois de uma pausa (500 ms); a tela só mostra: o selo "Conferindo…", "Sem erros" ou "N erros" (com texto e ícone), a lista de erros em português, o erro ao lado do campo e os avisos de autoria. **Gravar fica bloqueado com o motivo escrito** (erro, conferindo, nada mudou, ou "já tem mesa: salve uma cópia"). Alterações não gravadas pedem confirmação ao sair. Item de lista que se remove pede confirmação e diz o que some junto; o item novo abre sozinho e, depois de remover, o foco vai ao botão de acrescentar.

## Prévia (editor)

A prévia só se pede com a campanha sem erros (senão diz por quê) e mostra, em texto: o que o jogador vê, o que o mestre de IA recebe só com o público e o que recebe com os segredos, cada contexto recolhido num detalhe. Depois de uma edição ela é marcada como antiga, com o botão de atualizar no aviso. O tamanho do contexto do copiloto sai em números e em selo com texto e ícone (folga, perto do limite, passa do limite).

## Condições (editor)

Uma condição se escolhe, não se escreve: o tipo vem de uma lista fechada em frases ("O grupo está em", "Um NPC caiu"...) e o que ela cita, de uma lista dos itens que existem (ou um número, no turno). Trocar o tipo recomeça a condição no primeiro item. Cada lista diz o que significa vazia ("só o anfitrião move", "só o anfitrião revela") e que todas as condições precisam valer.

## Ação irreversível ou que gasta a vez

Pede confirmação **dentro do mesmo fluxo**, em uma frase completa que diz o efeito ("Mover o grupo para X.") e, em nota
própria embaixo, o custo ("Gasta a sua ação."): nunca as duas coladas numa linha só. Com "Voltar" e "Confirmar". O foco
vai ao texto, não ao "Confirmar". Ação que se desfaz sem custo (esquecer uma mesa guardada, remover um item do editor)
não pergunta: oferece **Desfazer** por alguns segundos.

**Ir não tem segundo passo.** A folha tem um passo só: as saídas como opções (a tocada na cena, ou a primeira, já
marcada) e, no rodapé, o botão que diz para onde o grupo vai ("Ir para Floresta Cinzenta"). O botão do rodapé já é a
confirmação: não se escolhe e depois se confirma.

## Folhas e diálogos

Cabeçalho (título + fechar por ícone, discreto), corpo, rodapé com **a secundária (Voltar, Cancelar) à esquerda e a
primária à direita** (`space-between`; um botão sozinho vai à direita). No celular sobe do pé; na tela larga é um
diálogo centralizado. Esc, toque no fundo e o botão de fechar saem sem escolher. O foco vai ao primeiro campo e volta
a quem abriu. Muitas opções: o rodapé fica fixo e o corpo rola.

## Mensagens de erro

Uma frase: o que aconteceu e, quando há, o que fazer. Sem id, código ou jargão. A tradução vive em
`core/api/api-failure.ts`, por código do servidor; código novo no servidor ganha texto lá. O texto do servidor é só
reserva (e a explicação de `command_refused`, que diz por que a regra recusou).

## Foco e anúncios

- Depois de navegar, o foco vai ao `h1`. Quando o elemento focado some, o foco vai ao que o substitui.
- Região viva só anuncia o que chega **depois** da carga inicial; o mesmo texto não é anunciado duas vezes.
- Informação operacional (já agiu, fora de combate, dano) leva texto ou ícone, nunca só cor.

## Informação técnica

Ids, códigos de atributo, fórmulas cruas e a saída de texto do CLI não aparecem. Fórmula vira "2d6 + Força";
dificuldade aparece pelo nome, com o número no detalhe.

## Navegar entre campanhas

A tela inicial é a **lista de campanhas em cards** (emblema, título, premissa em até 3 linhas, quantas mesas há neste
aparelho); tocar no card abre a campanha. Dentro dela, uma **barra lateral** leva às partes: Visão geral, Mesas e, só para quem abre
por localhost (o editor só atende a máquina do servidor), o Roteiro (Geral, Locais, NPCs, Facções, Marcos, Fatos, Prévia). Na tela larga (56rem) a barra é
uma coluna fixa; no celular fica recolhida atrás do botão "Menu", que abre os itens no lugar e diz o estado
(`aria-expanded`). O item da página atual leva `aria-current="page"` e uma marca na borda (não só a cor). A mesa em jogo
fica em tela cheia, sem barra, e volta à campanha por "← Campanha". Os endereços antigos (`/editor`, `/editor/<id>`)
levam ao roteiro da campanha.

## A história chega em fila

Todo texto novo da mesa (a nota do golpe, o desfecho, a narração, a fala do mestre e a resposta de `olhar`/`ficha`)
espera a sua vez numa **fila única** (`RevealQueue`, em `features/table/table.reveal.ts`): o primeiro espera um passo
(a resposta não surge junto do toque, como o mestre pensando), cada um espera os anteriores serem lidos (de 1 a 3 passos
de `--dv-reveal-step`, conforme o tamanho do texto) e um lote que chega com a fila andando espera ela acabar. O item só
entra no DOM quando chega a vez dele. **Não há exceção**: lote grande, movimento reduzido e toque no feed não pulam a
espera (a recarga da página, que só relê o histórico, entra de uma vez). Não há texto aparecendo letra a letra. Nada
disso bloqueia os botões.

**O painel lateral espera junto.** A cena (nome, descrição, saídas), o grupo (vida) e a ficha mostram a foto da mesa
só depois que todo texto daquela revisão apareceu; assim a cena nova ou a vida que caiu nunca antecipam a narração. O
que decide se dá para agir (botões, turno, quem agiu) usa sempre a foto viva.

**A tela acompanha a fila com rolagem suave.** Quando um item aparece, a tela é levada até ele com `behavior: smooth`
(direta com movimento reduzido), e termina na última ação. Não há mais o aviso "N novas".

## Sala de espera, pausa e fim

Criar uma mesa leva ao personagem e, depois dele, à **sala de espera** (a própria tela da mesa, em outra fase; o último
passo do caminho de entrada): o anfitrião vê quem já entrou e com que
personagem, o link do convite e o botão **Iniciar campanha**, bloqueado com o motivo escrito até haver um personagem;
quem foi convidado vê quem está aqui (já com o personagem criado) e "Esperando o anfitrião iniciar". A lista se
relê sozinha de poucos em poucos segundos. A história (abertura, primeiro marco) só começa ao iniciar.

Na barra do anfitrião, o bloco **Partida** (fixo no topo) mostra o tempo de jogo e o que a fase permite: Pausar ou Retomar, e **Encerrar**
(folha de confirmação que diz que ninguém mais age e que não dá para reabrir). Na **pausa** os jogadores só leem (aviso no
alto, dock bloqueado com o motivo) e o anfitrião continua; **encerrada**, todos só leem. O **tempo de jogo** (`dv-play-clock`,
"Rodando 1:23:45") anda sozinho a cada segundo enquanto a partida roda e fica parado na pausa e no fim; o leitor de tela
ouve só os minutos, sem anúncio segundo a segundo.
