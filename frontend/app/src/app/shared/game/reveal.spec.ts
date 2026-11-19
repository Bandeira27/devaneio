import { REVEAL_MAX_WEIGHT, revealTextLength, revealWeight } from './reveal';

describe('revealWeight', () => {
  it('um texto curto segura um passo; mais texto, mais passos, até o teto', () => {
    expect(revealWeight(6)).toBe(1);
    expect(revealWeight(0)).toBe(1);
    expect(revealWeight(100)).toBe(2);
    expect(revealWeight(200)).toBe(REVEAL_MAX_WEIGHT);
    expect(revealWeight(2000)).toBe(REVEAL_MAX_WEIGHT);
  });
});

describe('revealTextLength', () => {
  it('soma a narração e a nota de um evento, ou o texto da fala', () => {
    expect(revealTextLength({ type: 'event', narration: 'abc', note: 'de' })).toBe(5);
    expect(revealTextLength({ type: 'talk', text: 'abcd' })).toBe(4);
    expect(revealTextLength({ type: 'turn' })).toBe(0);
  });
});
