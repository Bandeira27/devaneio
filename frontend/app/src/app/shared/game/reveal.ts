import type { FeedItem } from './feed';

/** Quantos itens novos de uma vez ainda entram em fila: acima disso é uma carga grande (recarga) e entra tudo junto. */
export const REVEAL_MAX_QUEUE = 4;
/** Quantos caracteres se leem em um passo da fila (`--dv-reveal-step`); texto maior segura o próximo item por mais passos. */
export const REVEAL_CHARS_PER_STEP = 80;
/** O mais que um item segura o próximo, em passos: um texto longo não trava a fila. */
export const REVEAL_MAX_WEIGHT = 3;

/** O texto que a pessoa vai ler num item: a narração e a nota de um evento, ou a fala. */
function textOf(
  item: Pick<FeedItem, 'type'> & Partial<{ narration: string; note: string; text: string }>,
): number {
  return (item.narration?.length ?? 0) + (item.note?.length ?? 0) + (item.text?.length ?? 0);
}

/** Quantos passos de espera um item segura o seguinte: um por 80 caracteres, de 1 a 3 (o tempo de ler). */
export function revealWeight(item: Parameters<typeof textOf>[0]): number {
  return Math.min(REVEAL_MAX_WEIGHT, Math.max(1, Math.ceil(textOf(item) / REVEAL_CHARS_PER_STEP)));
}

/**
 * Em que passo da fila cada item novo de um lote entra (0 = na hora). Cada item espera os anteriores terminarem de ser
 * lidos: o passo dele é a soma do que os de antes seguram (`revealWeight`). O CSS multiplica o passo por
 * `--dv-reveal-step`, que é zero com movimento reduzido. Os marcadores de turno não esperam nem seguram ninguém. Um lote
 * maior que `REVEAL_MAX_QUEUE` entra todo de uma vez: a fila serve para acompanhar um golpe, não para ler uma recarga.
 */
export function revealSteps(items: readonly Parameters<typeof textOf>[0][]): number[] {
  const told = items.filter((item) => item.type !== 'turn').length;
  if (told > REVEAL_MAX_QUEUE) {
    return items.map(() => 0);
  }
  let next = 0;
  return items.map((item) => {
    if (item.type === 'turn') {
      return 0;
    }
    const step = next;
    next += revealWeight(item);
    return step;
  });
}
