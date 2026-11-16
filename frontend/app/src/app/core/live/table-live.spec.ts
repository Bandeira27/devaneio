import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { apiInterceptor } from '../api/api.interceptor';
import { SESSION_STORAGE, SessionStore } from '../session/session-store';
import { TableLive } from './table-live';

const TABLE = 'a'.repeat(16);

describe('TableLive', () => {
  let http: HttpTestingController;
  let live: TableLive;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([apiInterceptor])),
        provideHttpClientTesting(),
        { provide: SESSION_STORAGE, useValue: null },
      ],
    });
    TestBed.inject(SessionStore).save(TABLE, {
      token: 'tk',
      playerId: 'p2',
      role: 'player',
      title: 't',
      savedAt: 1,
    });
    http = TestBed.inject(HttpTestingController);
    live = TestBed.inject(TableLive);
  });

  const events = (): ReturnType<HttpTestingController['expectOne']> =>
    http.expectOne((r) => r.url === `/tables/${TABLE}/events`);

  it('liga o laço à API: primeira chamada sem espera, depois 20 s, com o token', async () => {
    const feed = live.open(TABLE, 80);
    const done = feed.run();
    const first = events();
    expect(first.request.params.get('wait')).toBe('0');
    expect(first.request.params.get('since')).toBe('30');
    expect(first.request.headers.get('Authorization')).toBe('Bearer tk');
    first.flush({ revision: 80, events: [], talk: [], talk_seq: 0 });
    await vi.waitFor(() => expect(feed.status()).toBe('live'));
    const second = await vi.waitFor(() => events());
    expect(second.request.params.get('wait')).toBe('20');
    expect(second.request.params.get('since')).toBe('80');
    feed.stop();
    await done;
    expect(second.cancelled).toBe(true); // stop() cancela a espera em andamento no servidor local
    http.verify();
  });

  it('401 do servidor encerra o fluxo como expirado', async () => {
    const feed = live.open(TABLE, 1);
    const done = feed.run();
    events().flush(
      { error: { code: 'unauthorized', message: 'token inválido' } },
      { status: 401, statusText: 'Unauthorized' },
    );
    await done;
    expect(feed.status()).toBe('expired');
  });

  it('mesa que sumiu (404) encerra o fluxo como "gone"', async () => {
    const feed = live.open(TABLE, 1);
    const done = feed.run();
    events().flush(
      { error: { code: 'table_not_found', message: 'mesa não encontrada' } },
      { status: 404, statusText: 'Not Found' },
    );
    await done;
    expect(feed.status()).toBe('gone');
  });

  it('abre um fluxo por chamada, independentes entre si', () => {
    const a = live.open(TABLE, 1);
    const b = live.open(TABLE, 1);
    expect(a).not.toBe(b);
  });
});
