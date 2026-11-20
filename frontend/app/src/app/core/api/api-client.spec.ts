import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { firstValueFrom } from 'rxjs';
import { SESSION_STORAGE, SessionStore } from '../session/session-store';
import { ApiClient } from './api-client';
import { ApiFailure } from './api-failure';
import { apiInterceptor } from './api.interceptor';

const TABLE = 'a'.repeat(16);

describe('ApiClient', () => {
  let api: ApiClient;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([apiInterceptor])),
        provideHttpClientTesting(),
        { provide: SESSION_STORAGE, useValue: null },
      ],
    });
    TestBed.inject(SessionStore).save(TABLE, {
      token: 'segredo-do-jogador',
      playerId: 'p2',
      role: 'player',
      title: 't',
      savedAt: 1,
    });
    api = TestBed.inject(ApiClient);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('manda o token da mesa no cabeçalho Authorization, nunca na URL', async () => {
    const result = firstValueFrom(api.table(TABLE));
    const request = http.expectOne(`/tables/${TABLE}`);
    expect(request.request.headers.get('Authorization')).toBe('Bearer segredo-do-jogador');
    expect(request.request.url).not.toContain('segredo');
    expect(request.request.urlWithParams).not.toContain('segredo');
    request.flush({ table_id: TABLE });
    expect(await result).toMatchObject({ table_id: TABLE });
  });

  it('não manda Authorization onde não há mesa (criar, entrar, listar)', async () => {
    void firstValueFrom(api.campaigns());
    expect(http.expectOne('/campaigns').request.headers.has('Authorization')).toBe(false);
    void firstValueFrom(api.createTable({ campaign_id: 'x', host_name: 'Ana' }));
    expect(http.expectOne('/tables').request.headers.has('Authorization')).toBe(false);
    void firstValueFrom(api.joinTable(TABLE, { invite_code: 'c', name: 'Bia' }));
    const join = http.expectOne(`/tables/${TABLE}/players`);
    expect(join.request.headers.has('Authorization')).toBe(false);
    expect(join.request.method).toBe('POST');
  });

  it('a prévia do convite é um POST sem Authorization, com o convite no corpo (nunca na URL)', () => {
    void firstValueFrom(api.invitePreview(TABLE, { invite_code: 'segredo-do-convite' }));
    const preview = http.expectOne(`/tables/${TABLE}/preview`);
    expect(preview.request.method).toBe('POST');
    expect(preview.request.headers.has('Authorization')).toBe(false);
    expect(preview.request.body).toEqual({ invite_code: 'segredo-do-convite' });
    expect(preview.request.urlWithParams).not.toContain('segredo');
  });

  it('não manda token de uma mesa que o navegador não conhece', () => {
    void firstValueFrom(api.table('b'.repeat(16))).catch(() => undefined);
    expect(http.expectOne(`/tables/${'b'.repeat(16)}`).request.headers.has('Authorization')).toBe(
      false,
    );
  });

  it('monta a consulta do long-poll', () => {
    void firstValueFrom(api.events(TABLE, { since: 7, sinceTalk: 3, sinceChat: 5, wait: 20 }));
    const request = http.expectOne((r) => r.url === `/tables/${TABLE}/events`);
    expect(request.request.params.get('since')).toBe('7');
    expect(request.request.params.get('since_talk')).toBe('3');
    expect(request.request.params.get('since_chat')).toBe('5');
    expect(request.request.params.get('wait')).toBe('20');
  });

  it('manda uma mensagem do chat com o token da mesa', () => {
    void firstValueFrom(api.postChat(TABLE, { text: 'bora' })).catch(() => undefined);
    const request = http.expectOne(`/tables/${TABLE}/chat`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ text: 'bora' });
  });

  it('manda comando e texto livre com a revisão', () => {
    void firstValueFrom(api.command(TABLE, { line: 'ir floresta', revision: 4 }));
    const command = http.expectOne(`/tables/${TABLE}/commands`);
    expect(command.request.body).toEqual({ line: 'ir floresta', revision: 4 });
    void firstValueFrom(api.say(TABLE, { text: 'olho em volta', revision: 4 }));
    expect(http.expectOne(`/tables/${TABLE}/say`).request.body).toEqual({
      text: 'olho em volta',
      revision: 4,
    });
  });

  it('lê regras e campanha da mesa', () => {
    void firstValueFrom(api.rules(TABLE));
    expect(http.expectOne(`/tables/${TABLE}/rules`).request.method).toBe('GET');
    void firstValueFrom(api.campaign(TABLE));
    expect(http.expectOne(`/tables/${TABLE}/campaign`).request.method).toBe('GET');
  });

  it('codifica o id da mesa na URL', () => {
    void firstValueFrom(api.table('a/../b')).catch(() => undefined);
    expect(http.expectOne((r) => r.url.startsWith('/tables/')).request.url).toBe(
      '/tables/a%2F..%2Fb',
    );
  });

  it('converte o erro do servidor em ApiFailure com o código e a mensagem', async () => {
    const result = firstValueFrom(api.command(TABLE, { line: 'x', revision: 1 }));
    http
      .expectOne(`/tables/${TABLE}/commands`)
      .flush(
        { error: { code: 'stale_revision', message: 'a mesa mudou' } },
        { status: 409, statusText: 'Conflict' },
      );
    const failure = await result.catch((e: unknown) => e);
    expect(failure).toBeInstanceOf(ApiFailure);
    expect(failure).toMatchObject({ status: 409, code: 'stale_revision', message: 'a mesa mudou' });
  });

  it('converte falha de rede em ApiFailure network', async () => {
    const result = firstValueFrom(api.table(TABLE));
    http.expectOne(`/tables/${TABLE}`).error(new ProgressEvent('error'));
    expect(await result.catch((e: unknown) => e)).toMatchObject({ status: 0, code: 'network' });
  });
});
