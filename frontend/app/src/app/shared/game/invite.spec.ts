import {
  inviteLink,
  isInviteCode,
  isLocalOrigin,
  isTableId,
  normalizeOrigin,
  parseInvite,
} from './invite';

const ID = '0123456789abcdef';
const CODE = 'Ab-_9xYz1234ABcd';

describe('convite', () => {
  it('monta o link com a mesa e o código no fragmento', () => {
    expect(inviteLink('http://192.168.0.5:8765', ID, CODE)).toBe(
      `http://192.168.0.5:8765/#/entrar/${ID}/${CODE}`,
    );
  });

  describe('parseInvite', () => {
    it.each([
      ['link inteiro', `http://192.168.0.5:8765/#/entrar/${ID}/${CODE}`],
      ['só o fragmento', `#/entrar/${ID}/${CODE}`],
      ['o caminho', `/entrar/${ID}/${CODE}`],
      ['com espaços em volta', `  http://x/#/entrar/${ID}/${CODE}  `],
      ['mesa e código separados por barra', `${ID}/${CODE}`],
      ['mesa e código separados por espaço', `${ID} ${CODE}`],
      ['mesa e código separados por dois pontos', `${ID}:${CODE}`],
    ])('lê %s', (_name, text) => {
      expect(parseInvite(text)).toEqual({ tableId: ID, code: CODE });
    });

    it.each([
      ['vazio', ''],
      ['texto qualquer', 'oi, tudo bem?'],
      ['mesa curta', `#/entrar/abc/${CODE}`],
      ['mesa em maiúsculas', `#/entrar/${ID.toUpperCase()}/${CODE}`],
      ['sem código', `#/entrar/${ID}/`],
      ['só a mesa', ID],
      ['código com caractere estranho', `${ID}/ab c`],
      ['código grande demais', `${ID}/${'a'.repeat(65)}`],
    ])('recusa %s', (_name, text) => {
      expect(parseInvite(text)).toBeNull();
    });

    it('não confunde um link comum com convite', () => {
      expect(parseInvite('https://exemplo.com/entrar/outra/coisa')).toBeNull();
    });
  });

  it('valida o formato do id da mesa e do código', () => {
    expect(isTableId(ID)).toBe(true);
    expect(isTableId('../etc')).toBe(false);
    expect(isTableId(ID + '0')).toBe(false);
    expect(isInviteCode(CODE)).toBe(true);
    expect(isInviteCode('com espaço')).toBe(false);
    expect(isInviteCode('')).toBe(false);
  });

  it.each([
    ['http://localhost:8765', true],
    ['http://127.0.0.1:8765', true],
    ['http://[::1]:8765', true],
    ['http://mesa.localhost:8765', true],
    ['http://192.168.0.5:8765', false],
    ['https://devaneio.exemplo.com', false],
    ['isto não é URL', false],
  ])('isLocalOrigin(%s) = %s', (origin, local) => {
    expect(isLocalOrigin(origin)).toBe(local);
  });

  describe('normalizeOrigin', () => {
    it.each([
      ['192.168.0.5:8765', 'http://192.168.0.5:8765'],
      ['http://192.168.0.5:8765', 'http://192.168.0.5:8765'],
      ['  http://mesa.local  ', 'http://mesa.local'],
      ['https://devaneio.exemplo.com/qualquer/coisa', 'https://devaneio.exemplo.com'],
      ['meu-pc', 'http://meu-pc'],
    ])('lê %j como %s', (text, origin) => {
      expect(normalizeOrigin(text)).toBe(origin);
    });

    it.each([
      ['', ''],
      ['só espaços', '   '],
      ['ftp', 'ftp://host'],
      ['javascript', 'javascript:alert(1)'],
      ['host quebrado', 'http://'],
    ])('recusa %s', (_name, text) => {
      expect(normalizeOrigin(text)).toBeNull();
    });
  });
});
