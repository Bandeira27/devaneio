import { RequestSequence } from './request-sequence';

describe('RequestSequence', () => {
  it('um pedido vale até aparecer outro mais novo', () => {
    const sequence = new RequestSequence();
    const first = sequence.begin();
    expect(first()).toBe(true);
    const second = sequence.begin();
    expect(first()).toBe(false);
    expect(second()).toBe(true);
  });

  it('invalidate() derruba o que estava em andamento, e um pedido novo volta a valer', () => {
    const sequence = new RequestSequence();
    const pending = sequence.begin();
    sequence.invalidate();
    expect(pending()).toBe(false);
    expect(sequence.begin()()).toBe(true);
  });
});
