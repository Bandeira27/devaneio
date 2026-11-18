import { clockText, currentSeconds, spokenTime } from './play-time';

describe('clockText', () => {
  it('mostra h:mm:ss, com as horas sem teto', () => {
    expect(clockText(0)).toBe('0:00:00');
    expect(clockText(65)).toBe('0:01:05');
    expect(clockText(3 * 3600 + 7 * 60 + 9)).toBe('3:07:09');
    expect(clockText(30 * 3600)).toBe('30:00:00');
  });

  it('nunca mostra tempo negativo nem fração', () => {
    expect(clockText(-5)).toBe('0:00:00');
    expect(clockText(59.9)).toBe('0:00:59');
  });
});

describe('spokenTime', () => {
  it('diz em palavras só até os minutos', () => {
    expect(spokenTime(10)).toBe('menos de um minuto');
    expect(spokenTime(60)).toBe('1 minuto');
    expect(spokenTime(23 * 60 + 40)).toBe('23 minutos');
    expect(spokenTime(3600)).toBe('1 hora');
    expect(spokenTime(3600 + 60)).toBe('1 hora e 1 minuto');
    expect(spokenTime(2 * 3600 + 23 * 60)).toBe('2 horas e 23 minutos');
  });
});

describe('currentSeconds', () => {
  it('enquanto roda, soma o tempo desde que o valor chegou', () => {
    expect(currentSeconds({ seconds: 100, running: true, receivedAt: 5_000 }, 12_400)).toBe(107);
  });

  it('parado (pausa, encerrada) fica no valor do servidor', () => {
    expect(currentSeconds({ seconds: 100, running: false, receivedAt: 5_000 }, 99_000)).toBe(100);
  });

  it('sem leitura ainda (receivedAt 0) não inventa tempo', () => {
    expect(currentSeconds({ seconds: 0, running: true, receivedAt: 0 }, 99_000)).toBe(0);
  });

  it('um relógio do navegador que voltou não dá tempo negativo', () => {
    expect(currentSeconds({ seconds: 50, running: true, receivedAt: 9_000 }, 1_000)).toBe(50);
  });
});
