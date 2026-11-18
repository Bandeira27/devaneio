import type { FeedItem } from './feed';

/** Quantos itens novos de uma vez ainda entram em fila: acima disso é uma carga grande (recarga) e entra tudo junto. */
export const REVEAL_MAX_QUEUE = 4;

/**
 * Em que passo da fila cada item novo de um lote entra (0 = na hora, 1 = um passo depois...). O CSS multiplica o passo
 * por `--dv-reveal-step`, que é zero com movimento reduzido. Os marcadores de turno não esperam (só abrem o capítulo).
 * Um lote maior que `REVEAL_MAX_QUEUE` entra todo de uma vez: a fila serve para acompanhar um golpe, não para ler
 * uma recarga.
 */
export function revealSteps(types: readonly FeedItem['type'][]): number[] {
  const told = types.filter((type) => type !== 'turn').length;
  if (told > REVEAL_MAX_QUEUE) {
    return types.map(() => 0);
  }
  let next = 0;
  return types.map((type) => {
    if (type === 'turn') {
      return 0;
    }
    return next++;
  });
}
