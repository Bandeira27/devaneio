import type { FeedItem } from './feed';

/** Quantos caracteres se leem em um passo da fila (`--dv-reveal-step`); texto maior segura o próximo item por mais passos. */
export const REVEAL_CHARS_PER_STEP = 80;
/** O mais que um item segura o próximo, em passos: um texto longo não trava a fila. */
export const REVEAL_MAX_WEIGHT = 3;

/** O texto que a pessoa vai ler num item: a narração e a nota de um evento, ou a fala. */
export function revealTextLength(
  item: Pick<FeedItem, 'type'> & Partial<{ narration: string; note: string; text: string }>,
): number {
  return (item.narration?.length ?? 0) + (item.note?.length ?? 0) + (item.text?.length ?? 0);
}

/**
 * Quantos passos de espera um texto segura o seguinte: um por 80 caracteres, de 1 a 3 (o tempo de ler). Vale para todo
 * texto novo, sem exceção: não há lote que entre de uma vez.
 */
export function revealWeight(textLength: number): number {
  return Math.min(REVEAL_MAX_WEIGHT, Math.max(1, Math.ceil(textLength / REVEAL_CHARS_PER_STEP)));
}
