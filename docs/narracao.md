# Narração

Como a prosa é gerada a partir dos eventos.

A narração é uma camada de exibição: o estado guarda só o texto mecânico de cada evento, e
`devaneio.narration.Narrator` transforma evento em prosa a partir de um **pacote de narração**
(JSON, estilo Tracery): regras com alternativas, expansão recursiva de `#simbolo#` e variáveis
do evento (`#ator#`, `#alvo#`, `#arma#`, ...). A regra é escolhida por tipo e variante
(`check.success`, `damage.golpe_queda`, `director.tenso`...); evento sem regra sai com o texto
mecânico. A variedade vem de um RNG próprio semeado por (semente da partida, índice do evento):
reproduzível, e sem tocar na aleatoriedade do jogo. Pacotes são validados na carga: toda
referência precisa ser regra ou variável do tipo de evento. Quando houver LLM, ele entra por
este mesmo contrato: evento entra, prosa sai.
