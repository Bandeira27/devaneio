import { whenOf } from './when';

const NOW = new Date(2026, 10, 16, 15, 0).getTime();
const ago = (days: number, hour = 9): number => new Date(2026, 10, 16 - days, hour).getTime();

describe('whenOf', () => {
  it('conta por dia do calendário, não por 24 horas', () => {
    expect(whenOf(ago(0, 1), NOW)).toBe('hoje');
    expect(whenOf(ago(1, 23), NOW)).toBe('ontem');
    expect(whenOf(ago(3), NOW)).toBe('há 3 dias');
  });

  it('depois de uma semana mostra a data', () => {
    expect(whenOf(ago(10), NOW)).toMatch(/6/);
  });
});
