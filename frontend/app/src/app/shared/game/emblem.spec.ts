import { campaignEmblem } from './emblem';

describe('campaignEmblem', () => {
  it('é sempre o mesmo para o mesmo id', () => {
    expect(campaignEmblem('sombra-do-vale')).toEqual(campaignEmblem('sombra-do-vale'));
  });

  it('usa só ícones e tons dos conjuntos fechados', () => {
    for (const id of ['a', 'sombra-do-vale', 'minha_campanha_2', 'x'.repeat(40)]) {
      const emblem = campaignEmblem(id);
      expect(['book', 'map', 'flag', 'scroll', 'eye', 'person']).toContain(emblem.icon);
      expect(['accent', 'info', 'ok', 'warn']).toContain(emblem.tone);
    }
  });

  it('ids diferentes espalham os emblemas (nem todos iguais)', () => {
    const emblems = new Set(
      Array.from({ length: 20 }, (_, i) => JSON.stringify(campaignEmblem(`campanha-${i}`))),
    );
    expect(emblems.size).toBeGreaterThan(3);
  });
});
