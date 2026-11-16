import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ApiClient } from '@core/api/api-client';
import { apiInterceptor } from '@core/api/api.interceptor';
import { TABLE_ID } from '../../testing/fixtures';
import { TableActions } from './table.actions';
import type { TableSnapshot } from './table.snapshot';

const ok = (over: object = {}) => ({
  revision: 4,
  events: [],
  text: '',
  status: 'active',
  turn_ended: false,
  ...over,
});

function setup() {
  TestBed.configureTestingModule({
    providers: [provideHttpClient(withInterceptors([apiInterceptor])), provideHttpClientTesting()],
  });
  const http = TestBed.inject(HttpTestingController);
  let revision = 3;
  const refresh = vi.fn(async () => {
    revision += 1;
  });
  const snapshot = { revision: () => revision, refresh } as unknown as TableSnapshot;
  const actions = new TableActions(TestBed.inject(ApiClient), () => TABLE_ID, snapshot);
  return { http, actions, refresh };
}
const tick = () => new Promise((resolve) => setTimeout(resolve));

describe('TableActions', () => {
  it('manda o comando com a revisão atual, guarda a resposta de texto e pede a foto nova', async () => {
    const { http, actions, refresh } = setup();
    const done = actions.run('olhar');
    const request = http.expectOne(`/tables/${TABLE_ID}/commands`);
    expect(request.request.body).toEqual({ line: 'olhar', revision: 3 });
    request.flush(ok({ text: 'Você vê uma vila.' }));
    expect(await done).toBe(true);
    expect(actions.reply()).toBe('Você vê uma vila.');
    expect(refresh).toHaveBeenCalledOnce();
    expect(actions.busy()).toBe(false);
  });

  it('o texto livre guarda a fala do mestre quando não houve evento', async () => {
    const { http, actions } = setup();
    const done = actions.say('Olho o altar.');
    http
      .expectOne(`/tables/${TABLE_ID}/say`)
      .flush({ ...ok(), say: 'O altar range.', commands: [] });
    await done;
    expect(actions.reply()).toBe('O altar range.');
  });

  it('com a resposta trazendo eventos, a tela mostra o feed e não a resposta', async () => {
    const { http, actions } = setup();
    const done = actions.run('ir floresta');
    const event = { index: 1, turn: 0, kind: 'move', text: 'm', prose: 'p', narration: null };
    http.expectOne(`/tables/${TABLE_ID}/commands`).flush(ok({ events: [event], text: 'Floresta' }));
    await done;
    expect(actions.reply()).toBe('');
  });

  it('ignora uma segunda ação enquanto a primeira está em voo', async () => {
    const { http, actions } = setup();
    const first = actions.run('olhar');
    expect(actions.busy()).toBe(true);
    expect(await actions.run('ficha')).toBe(false);
    http.expectOne(`/tables/${TABLE_ID}/commands`).flush(ok());
    expect(await first).toBe(true);
  });

  it('em stale_revision relê a foto e repete uma vez com a revisão nova', async () => {
    const { http, actions, refresh } = setup();
    const done = actions.run('olhar');
    http
      .expectOne(`/tables/${TABLE_ID}/commands`)
      .flush(
        { error: { code: 'stale_revision', message: 'A mesa mudou.' } },
        { status: 409, statusText: 'Conflict' },
      );
    await tick();
    const retry = http.expectOne(`/tables/${TABLE_ID}/commands`);
    expect((retry.request.body as { revision: number }).revision).toBe(4);
    retry.flush(ok());
    expect(await done).toBe(true);
    expect(refresh).toHaveBeenCalledTimes(2); // a releitura do retry e a do fim da ação
  });

  it('um erro do servidor vira texto e libera a próxima ação', async () => {
    const { http, actions } = setup();
    const done = actions.run('dança');
    http
      .expectOne(`/tables/${TABLE_ID}/commands`)
      .flush(
        { error: { code: 'bad_command', message: 'Comando desconhecido.' } },
        { status: 422, statusText: 'x' },
      );
    expect(await done).toBe(false);
    expect(actions.error()).toBe('Comando desconhecido.');
    expect(actions.busy()).toBe(false);
  });
});
