import {
  CommandError,
  END_TURN,
  MAX_SOURCE,
  REST,
  attack,
  beat,
  check,
  go,
  heal,
  hurt,
  join,
  quote,
  reveal,
} from './commands';
import { MAX_ARG, normalizeName } from './names';

describe('comandos', () => {
  it('monta ir, testar e atacar como o servidor espera', () => {
    expect(go('floresta')).toBe('ir floresta');
    expect(check('lutar', 'normal')).toBe('testar lutar normal');
    expect(check('lutar', 'normal', 'vantagem')).toBe('testar lutar normal vantagem');
    expect(check('lutar', 'normal', null)).toBe('testar lutar normal');
    expect(attack('adaga', 'sacerdote')).toBe('atacar adaga sacerdote');
    expect(attack('punhos', 'bram', 'desvantagem')).toBe('atacar punhos bram desvantagem');
  });

  it.each([
    ['com espaço', 'ir floresta; fim'],
    ['com aspas', 'a"b'],
    ['com barra', '../x'],
    ['vazio', ''],
    ['começando por hífen', '-x'],
    ['com dois pontos (vira prefixo de ator)', 'aria:'],
    ['com quebra de linha', 'a\nb'],
    ['grande demais', 'a'.repeat(MAX_ARG + 1)],
  ])('recusa id %s antes de virar comando', (_name, id) => {
    expect(() => go(id)).toThrow(CommandError);
    expect(() => check(id, 'normal')).toThrow(CommandError);
    expect(() => check('lutar', id)).toThrow(CommandError);
    expect(() => check('lutar', 'normal', id === '' ? 'x y' : id)).toThrow(CommandError);
    expect(() => attack('punhos', id)).toThrow(CommandError);
    expect(() => attack(id, 'bram')).toThrow(CommandError);
  });

  describe('entrar', () => {
    it('monta o id, o nome entre aspas e os atributos', () => {
      expect(join('aria', 'Aria', { FOR: 3, AGI: 2 })).toBe('entrar aria "Aria" FOR=3 AGI=2');
      expect(join('aria', 'Aria', {})).toBe('entrar aria "Aria"');
    });

    it('escapa aspas e barra do nome para o shlex do servidor', () => {
      expect(quote('Ana "Fera" Lima')).toBe('"Ana \\"Fera\\" Lima"');
      expect(quote('a\\b')).toBe('"a\\\\b"');
      expect(join('ana', 'Ana "Fera"', {})).toBe('entrar ana "Ana \\"Fera\\""');
    });

    it('um nome com ponto e vírgula ou dois pontos fica preso entre as aspas', () => {
      expect(join('ana', 'x; fim', {})).toBe('entrar ana "x; fim"');
      expect(join('ana', 'ordem: ir', {})).toBe('entrar ana "ordem: ir"');
    });

    it('normaliza o nome (NFKC e espaços)', () => {
      expect(join('ana', '  Ana   Lima  ', {})).toBe('entrar ana "Ana Lima"');
      expect(normalizeName('ＡＢＣ')).toBe('ABC');
    });

    it.each([
      ['atributo em minúsculas', { for: 3 }],
      ['atributo com espaço', { 'F O': 3 }],
      ['valor fracionário', { FOR: 2.5 }],
      ['valor infinito', { FOR: Number.POSITIVE_INFINITY }],
    ])('recusa %s', (_name, attributes) => {
      expect(() => join('ana', 'Ana', attributes)).toThrow(CommandError);
    });

    it('recusa nome vazio ou com caractere de controle', () => {
      expect(() => join('ana', '   ', {})).toThrow('Dê um nome');
      expect(() => join('ana', 'a‮b', {})).toThrow('controle');
      expect(() => join('ana', 'a\u0007b', {})).toThrow('controle');
    });
  });
});

describe('comandos do anfitrião', () => {
  it('monta marco, revelar, ferir, curar, fim e descansar', () => {
    expect(beat('ativar', 'chegada')).toBe('marco ativar chegada');
    expect(beat('concluir', 'x')).toBe('marco concluir x');
    expect(reveal('altar')).toBe('revelar altar');
    expect(hurt('bram', 3)).toBe('ferir bram 3');
    expect(hurt('bram', 3, '  a queda ')).toBe('ferir bram 3 "a queda"');
    expect(heal('bia', 2, 'poção "forte"')).toBe('curar bia 2 "poção \\"forte\\""');
    expect(END_TURN).toBe('fim');
    expect(REST).toBe('descansar');
  });

  it('recusa id, quantia e fonte que virariam outro comando', () => {
    expect(() => beat('ativar', 'a b')).toThrow(CommandError);
    expect(() => reveal('x; fim')).toThrow(CommandError);
    expect(() => hurt('bram; fim', 1)).toThrow(CommandError);
    for (const amount of [0, -1, 1.5, 1000, Number.NaN]) {
      expect(() => hurt('bram', amount)).toThrow(CommandError);
    }
    expect(() => heal('bia', 1, 'a'.repeat(MAX_SOURCE + 1))).toThrow(CommandError);
  });
});
