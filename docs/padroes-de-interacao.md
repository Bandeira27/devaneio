# Padrões de interação

Como o app do jogador se comporta, para que telas diferentes se sintam iguais. O visual está em
[`design-system.md`](design-system.md) e o movimento em [`movimento.md`](movimento.md). Quem revisa usa a skill
[`review-ui`](../.agents/skills/review-ui/SKILL.md).

## Estados de uma tela ou região

| Estado                        | O que mostrar                                                                       | Componente                         |
| ----------------------------- | ----------------------------------------------------------------------------------- | ---------------------------------- |
| Carregando                    | texto curto do que está sendo aberto; sem esqueleto piscando                        | `dv-state` `loading`               |
| Vazio                         | o que falta e o próximo passo ("Ninguém mais entrou. Convide o grupo")              | `dv-state`                         |
| Erro                          | o que houve em frase humana **e** uma saída: "Tentar de novo" ou "Voltar ao início" | `dv-state` `error`                 |
| Sem conexão                   | badge discreto no cabeçalho; ações **bloqueadas com o motivo**                      | `dv-connection-badge`, `dvBlocked` |
| Sessão vencida ou mesa sumida | aviso com saída; a sessão guardada é esquecida                                      | `dv-notice`                        |

Nenhuma tela fica sem saída: erro e vazio sempre oferecem uma ação.

## Transição entre telas

- O cabeçalho é a âncora: fica parado e só a página "vira" (sai para a esquerda, entra da direita, um deslocamento curto).
- Se a troca demora mais de 150 ms (código ou dados), uma **folha de transição** cobre a página que estava saindo, com a
  marca e "Abrindo…", e fica por no mínimo 300 ms para não piscar. A região principal ganha `aria-busy` e o leitor de tela
  ouve "Abrindo…". Troca rápida nunca mostra a folha.
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

## Ação irreversível ou que gasta a vez

Pede confirmação **dentro do mesmo fluxo**, em uma frase que diz o efeito ("Mover o grupo para X. Gasta a sua ação."),
com "Voltar" e "Confirmar". O foco vai ao texto, não ao "Confirmar". Ação que se desfaz sem custo (esquecer uma mesa
guardada) não pergunta: oferece **Desfazer** por alguns segundos.

## Folhas e diálogos

Cabeçalho (título + fechar por ícone), corpo, rodapé com a ação primária. No celular sobe do pé; na tela larga é um
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
