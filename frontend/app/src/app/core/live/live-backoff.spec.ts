import { backoffDelay } from './live-backoff';

describe('backoffDelay', () => {
  it('dobra a cada falha, de 1 s até o teto de 15 s', () => {
    const delays = [0, 1, 2, 3, 4, 5, 9].map((attempt) => backoffDelay(attempt, 0.5));
    expect(delays).toEqual([1000, 2000, 4000, 8000, 15_000, 15_000, 15_000]);
  });

  it('o jitter vai de -20% a +20%', () => {
    expect(backoffDelay(0, 0)).toBe(800);
    expect(backoffDelay(0, 1)).toBe(1200);
  });
});
