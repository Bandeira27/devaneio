import { TestBed } from '@angular/core/testing';
import { ApiFailure } from '../api/api-failure';
import {
  MAX_TABLES,
  SESSION_STORAGE,
  STORAGE_KEY,
  SessionStore,
  StoredTable,
} from './session-store';

const A = 'a'.repeat(16);
const B = 'b'.repeat(16);

function entry(over: Partial<StoredTable> = {}): StoredTable {
  return {
    token: 'token-1',
    playerId: 'p2',
    role: 'player',
    title: 'A Sombra do Vale',
    savedAt: 100,
    ...over,
  };
}

class FakeStorage {
  readonly data = new Map<string, string>();
  fail = false;
  getItem(key: string): string | null {
    return this.data.get(key) ?? null;
  }
  setItem(key: string, value: string): void {
    if (this.fail) {
      throw new Error('cheio');
    }
    this.data.set(key, value);
  }
}

function store(storage: FakeStorage | null): SessionStore {
  TestBed.configureTestingModule({
    providers: [{ provide: SESSION_STORAGE, useValue: storage }],
  });
  return TestBed.inject(SessionStore);
}

describe('SessionStore', () => {
  it('guarda e devolve a mesa, o token e persiste no armazenamento', () => {
    const storage = new FakeStorage();
    const sessions = store(storage);
    sessions.save(A, entry());
    expect(sessions.get(A)?.playerId).toBe('p2');
    expect(sessions.tokenOf(A)).toBe('token-1');
    expect(JSON.parse(storage.data.get(STORAGE_KEY) ?? '{}')[A].token).toBe('token-1');
  });

  it('lista da mais recente para a mais antiga', () => {
    const sessions = store(new FakeStorage());
    sessions.save(A, entry({ savedAt: 1 }));
    sessions.save(B, entry({ savedAt: 2 }));
    expect(sessions.list().map((t) => t.tableId)).toEqual([B, A]);
  });

  it('esquece uma mesa', () => {
    const storage = new FakeStorage();
    const sessions = store(storage);
    sessions.save(A, entry());
    sessions.forget(A);
    expect(sessions.get(A)).toBeNull();
    expect(sessions.tokenOf(A)).toBeNull();
    expect(JSON.parse(storage.data.get(STORAGE_KEY) ?? '{}')).toEqual({});
  });

  it.each([
    [401, true],
    [404, true],
    [500, false],
    [0, false],
  ])('com o status %i a mesa é esquecida: %s', (status, forgotten) => {
    const sessions = store(new FakeStorage());
    sessions.save(A, entry());
    sessions.forgetIfLost(A, new ApiFailure(status, 'x', 'm'));
    expect(sessions.get(A) === null).toBe(forgotten);
  });

  it('um erro que não é da API não faz esquecer a mesa', () => {
    const sessions = store(new FakeStorage());
    sessions.save(A, entry());
    sessions.forgetIfLost(A, new Error('qualquer'));
    expect(sessions.get(A)).not.toBeNull();
  });

  it('recarrega o que foi guardado', () => {
    const storage = new FakeStorage();
    storage.data.set(
      STORAGE_KEY,
      JSON.stringify({ [A]: entry({ role: 'host', invite: 'convite' }) }),
    );
    const sessions = store(storage);
    expect(sessions.get(A)).toMatchObject({ role: 'host', invite: 'convite' });
  });

  it('funciona só na memória quando não há armazenamento', () => {
    const sessions = store(null);
    sessions.save(A, entry());
    expect(sessions.tokenOf(A)).toBe('token-1');
  });

  it('continua na memória quando gravar falha (sem espaço, sem permissão)', () => {
    const storage = new FakeStorage();
    storage.fail = true;
    const sessions = store(storage);
    expect(() => sessions.save(A, entry())).not.toThrow();
    expect(sessions.tokenOf(A)).toBe('token-1');
  });

  it.each([
    ['JSON quebrado', '{ não é json'],
    ['uma lista', '[1, 2]'],
    ['um número', '42'],
    ['null', 'null'],
  ])('ignora o armazenamento com %s', (_name, raw) => {
    const storage = new FakeStorage();
    storage.data.set(STORAGE_KEY, raw);
    expect(store(storage).list()).toEqual([]);
  });

  it('descarta entradas inválidas e mantém as válidas', () => {
    const storage = new FakeStorage();
    storage.data.set(
      STORAGE_KEY,
      JSON.stringify({
        [A]: entry(),
        [B]: { ...entry(), role: 'admin' },
        ['curto']: entry(),
        ['c'.repeat(16)]: { ...entry(), token: '' },
        ['d'.repeat(16)]: { ...entry(), playerId: '../x' },
        ['e'.repeat(16)]: { ...entry(), token: 'x'.repeat(201) },
        ['f'.repeat(16)]: { ...entry(), savedAt: 'ontem' },
        ['0'.repeat(16)]: 'texto',
      }),
    );
    expect(
      store(storage)
        .list()
        .map((t) => t.tableId),
    ).toEqual([A]);
  });

  it('anota a campanha de uma mesa guardada sem mexer na ordem nem nos outros dados', () => {
    const sessions = store(new FakeStorage());
    sessions.save(A, entry({ savedAt: 1 }));
    sessions.save(B, entry({ savedAt: 2 }));
    sessions.tag(A, 'sombra-do-vale');
    expect(sessions.get(A)?.campaignId).toBe('sombra-do-vale');
    expect(sessions.get(A)?.savedAt).toBe(1);
    expect(sessions.list().map((t) => t.tableId)).toEqual([B, A]);
    sessions.tag('c'.repeat(16), 'x'); // mesa que não está guardada: nada acontece
    expect(sessions.list()).toHaveLength(2);
  });

  it('não aceita id de mesa fora do formato que o servidor gera', () => {
    const sessions = store(new FakeStorage());
    sessions.save('../etc/passwd', entry());
    sessions.save('ABC', entry());
    expect(sessions.list()).toEqual([]);
  });

  it(`guarda no máximo ${MAX_TABLES} mesas, descartando as mais antigas`, () => {
    const sessions = store(new FakeStorage());
    for (let i = 0; i < MAX_TABLES + 3; i++) {
      sessions.save(i.toString(16).padStart(16, '0'), entry({ savedAt: i }));
    }
    const ids = sessions.list().map((t) => t.tableId);
    expect(ids).toHaveLength(MAX_TABLES);
    expect(ids).not.toContain('0'.repeat(16));
    expect(ids[0]).toBe((MAX_TABLES + 2).toString(16).padStart(16, '0'));
  });
});
