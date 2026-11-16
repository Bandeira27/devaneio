const BACKOFF_BASE_MS = 1000;
const BACKOFF_MAX_MS = 15_000;

/**
 * Quanto esperar antes da tentativa seguinte depois de `attempt` falhas seguidas: dobra a cada vez, de 1 s até 15 s,
 * com ±20% de jitter para que abas que caíram juntas não voltem juntas.
 *
 * @param attempt Quantas falhas seguidas já houve (0 na primeira).
 * @param random Um sorteio entre 0 e 1 (`Math.random`, ou um valor fixo nos testes).
 */
export function backoffDelay(attempt: number, random: number): number {
  const base = Math.min(BACKOFF_MAX_MS, BACKOFF_BASE_MS * 2 ** attempt);
  return Math.round(base * (0.8 + 0.4 * random));
}
