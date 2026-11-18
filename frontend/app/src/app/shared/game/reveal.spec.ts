import { REVEAL_MAX_QUEUE, revealSteps } from './reveal';

describe('revealSteps', () => {
  it('um item sozinho entra na hora', () => {
    expect(revealSteps(['event'])).toEqual([0]);
  });

  it('os itens de um golpe entram um de cada vez, na ordem', () => {
    expect(revealSteps(['event', 'event', 'talk'])).toEqual([0, 1, 2]);
  });

  it('o marcador de turno não espera nem ocupa passo', () => {
    expect(revealSteps(['turn', 'event', 'talk'])).toEqual([0, 0, 1]);
  });

  it('um lote grande (recarga) entra todo de uma vez', () => {
    const lote = Array.from({ length: REVEAL_MAX_QUEUE + 1 }, () => 'event' as const);
    expect(revealSteps(lote).every((step) => step === 0)).toBe(true);
  });

  it('o limite da fila ainda entra em fila', () => {
    const lote = Array.from({ length: REVEAL_MAX_QUEUE }, () => 'event' as const);
    expect(revealSteps(lote)).toEqual([0, 1, 2, 3]);
  });

  it('lista vazia', () => {
    expect(revealSteps([])).toEqual([]);
  });
});
