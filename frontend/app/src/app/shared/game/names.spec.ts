import { go } from './commands';
import { MAX_ARG, normalizeName, slugify, uniqueId, validateName } from './names';

describe('nomes e ids', () => {
  it('normaliza acentos compostos e espaços', () => {
    expect(normalizeName('  Ana   Lima ')).toBe('Ana Lima');
    expect(normalizeName('Ａｒｉａ')).toBe('Aria'); // largura total vira normal (NFKC)
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
