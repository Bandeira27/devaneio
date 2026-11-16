import { TABLE_ID, isEntry } from './session-entry';

const valid = { token: 't', playerId: 'p2', role: 'player', title: 'x', savedAt: 1 };

describe('isEntry', () => {
  it('aceita uma entrada completa, com ou sem convite', () => {
    expect(isEntry(valid)).toBe(true);
    expect(isEntry({ ...valid, role: 'host', invite: 'abc' })).toBe(true);
  });

  it.each([
    ['não é objeto', 'texto'],
    ['é nulo', null],
    ['token vazio', { ...valid, token: '' }],
    ['token enorme', { ...valid, token: 'a'.repeat(201) }],
    ['jogador fora do formato', { ...valid, playerId: 'ana' }],
    ['papel desconhecido', { ...valid, role: 'admin' }],
    ['título enorme', { ...valid, title: 'a'.repeat(201) }],
    ['convite que não é texto', { ...valid, invite: 5 }],
    ['data que não é número finito', { ...valid, savedAt: Number.NaN }],
  ])('recusa quando %s', (_motivo, value) => {
    expect(isEntry(value)).toBe(false);
  });
});

describe('TABLE_ID', () => {
  it('só aceita o formato que o servidor gera', () => {
    expect(TABLE_ID.test('0123456789abcdef')).toBe(true);
    expect(TABLE_ID.test('../../x')).toBe(false);
    expect(TABLE_ID.test('0123456789ABCDEF')).toBe(false);
  });
});
