import {
  CommandError,
  MAX_ARG,
  attack,
  check,
  go,
  join,
  normalizeName,
  quote,
  slugify,
  uniqueId,
  validateName,
} from './commands';

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

  describe('nomes', () => {
    it('valida o tamanho e os caracteres', () => {
      expect(validateName('Aria')).toBeNull();
      expect(validateName('a'.repeat(MAX_ARG))).toBeNull();
      expect(validateName('a'.repeat(MAX_ARG + 1))).toContain(`${MAX_ARG}`);
      expect(validateName('')).toContain('Dê um nome');
      expect(validateName('a​b')).toContain('invisíveis');
    });
  });

  describe('slugify e uniqueId', () => {
    it.each([
      ['Aria', 'aria'],
      ['João da Silva', 'joao-da-silva'],
      ['Çélia Ñandú', 'celia-nandu'],
      ['  --Zé!!  ', 'ze'],
      ['Ana "Fera" Lima', 'ana-fera-lima'],
      ['!!!', 'personagem'],
      ['', 'personagem'],
      ['a'.repeat(60), 'a'.repeat(24)],
      ['abc def ghi jkl mno pqr stu', 'abc-def-ghi-jkl-mno-pqr'],
    ])('slugify(%j) = %j', (name, slug) => {
      expect(slugify(name)).toBe(slug);
    });

    it('todo slug gerado serve de id num comando', () => {
      for (const name of ['João', 'x y z', '123', 'A-b_c', 'ÀÉÎÕÜ']) {
        expect(() => go(slugify(name))).not.toThrow();
      }
    });

    it('acrescenta um sufixo quando o id já está em uso', () => {
      expect(uniqueId('aria', [])).toBe('aria');
      expect(uniqueId('aria', ['zed'])).toBe('aria');
      expect(uniqueId('aria', ['aria'])).toBe('aria-2');
      expect(uniqueId('aria', ['aria', 'aria-2', 'aria-3'])).toBe('aria-4');
      expect(uniqueId('sacerdote', new Set(['sacerdote']))).toBe('sacerdote-2');
    });
  });
});
