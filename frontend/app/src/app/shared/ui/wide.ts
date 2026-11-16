/**
 * A tela é larga (a partir de 64rem)? É o mesmo ponto de quebra das media queries de `styles/` e das telas, que não
 * aceitam token. Lido na hora de usar: vale para o que dura segundos (abrir uma folha), não reage a girar o aparelho.
 */
export function isWide(): boolean {
  return typeof matchMedia === 'function' && matchMedia('(min-width: 64rem)').matches;
}
