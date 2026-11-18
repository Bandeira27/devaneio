import { REVEAL_MAX_QUEUE, REVEAL_MAX_WEIGHT, revealSteps, revealWeight } from './reveal';

const short = { type: 'event' as const, narration: 'Curta.', note: 'nota' };
const long = { type: 'talk' as const, text: 'x'.repeat(200) };
const turn = { type: 'turn' as const };

describe('revealWeight', () => {
  it('um texto curto segura um passo; mais texto, mais passos, até o teto', () => {
    expect(revealWeight(short)).toBe(1);
    expect(revealWeight({ type: 'talk', text: 'x'.repeat(100) })).toBe(2);
    expect(revealWeight(long)).toBe(REVEAL_MAX_WEIGHT);
    expect(revealWeight({ type: 'talk', text: 'x'.repeat(2000) })).toBe(REVEAL_MAX_WEIGHT);
  });
});

describe('revealSteps', () => {
  it('um item sozinho entra na hora', () => {
    expect(revealSteps([short])).toEqual([0]);
  });

  it('cada item espera os anteriores serem lidos: o passo é a soma do que eles seguram', () => {
    expect(revealSteps([short, short, long])).toEqual([0, 1, 2]);
    expect(revealSteps([long, short])).toEqual([0, REVEAL_MAX_WEIGHT]);
  });

  it('o marcador de turno não espera nem segura ninguém', () => {
    expect(revealSteps([turn, short, short])).toEqual([0, 0, 1]);
  });

  it('um lote grande (recarga) entra todo de uma vez', () => {
    const lote = Array.from({ length: REVEAL_MAX_QUEUE + 1 }, () => short);
    expect(revealSteps(lote).every((step) => step === 0)).toBe(true);
  });

  it('o limite da fila ainda entra em fila', () => {
    const lote = Array.from({ length: REVEAL_MAX_QUEUE }, () => short);
    expect(revealSteps(lote)).toEqual([0, 1, 2, 3]);
  });

  it('lista vazia', () => {
    expect(revealSteps([])).toEqual([]);
  });
});
