import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ApiClient } from '@core/api/api-client';
import { apiInterceptor } from '@core/api/api.interceptor';
import { TABLE_ID } from '../../../testing/fixtures';
import { CopilotActions } from './copilot.actions';

function setup() {
  TestBed.configureTestingModule({
    providers: [provideHttpClient(withInterceptors([apiInterceptor])), provideHttpClientTesting()],
  });
  const http = TestBed.inject(HttpTestingController);
  return { http, copilot: new CopilotActions(TestBed.inject(ApiClient), () => TABLE_ID) };
}
const url = `/tables/${TABLE_ID}/copilot`;

describe('CopilotActions', () => {
  it('manda a pergunta e guarda a resposta e sobre o que ela é', async () => {
    const { http, copilot } = setup();
    const done = copilot.ask('Qual o próximo marco?');
    expect(copilot.busy()).toBe(true);
    const request = http.expectOne(url);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ text: 'Qual o próximo marco?' });
    request.flush({ text: 'Ative o altar.' });
    expect(await done).toBe(true);
    expect(copilot.answer()).toBe('Ative o altar.');
    expect(copilot.asked()).toBe('Qual o próximo marco?');
    expect(copilot.busy()).toBe(false);
    expect(copilot.error()).toBe('');
  });

  it('uma pergunta de cada vez', async () => {
    const { http, copilot } = setup();
    const first = copilot.ask('a');
    expect(await copilot.ask('b')).toBe(false);
    http.expectOne(url).flush({ text: 'ok' });
    await first;
    http.verify();
  });

  it('a próxima pergunta apaga a resposta anterior', async () => {
    const { http, copilot } = setup();
    const first = copilot.ask('a');
    http.expectOne(url).flush({ text: 'um' });
    await first;
    const second = copilot.ask('b');
    expect(copilot.answer()).toBe('');
    http.expectOne(url).flush({ text: 'dois' });
    await second;
    expect(copilot.answer()).toBe('dois');
  });

  it.each([
    [409, 'copilot_busy', 'O copiloto ainda está respondendo. Espere um instante.'],
    [429, 'copilot_rate_limited', 'O copiloto precisa de um instante antes da próxima pergunta.'],
    [422, 'context_too_large', 'A campanha é grande demais para o copiloto responder.'],
    [409, 'llm_disabled', 'Esta mesa não tem mestre de IA ligado.'],
  ])('a recusa %i %s vira uma frase e libera a próxima pergunta', async (status, code, text) => {
    const { http, copilot } = setup();
    const done = copilot.ask('a');
    http.expectOne(url).flush({ error: { code, message: 'x' } }, { status, statusText: 'x' });
    expect(await done).toBe(false);
    expect(copilot.error()).toBe(text);
    expect(copilot.answer()).toBe('');
    expect(copilot.busy()).toBe(false);
  });

  it('a resposta nunca vai ao armazenamento do navegador', async () => {
    const { http, copilot } = setup();
    const before = JSON.stringify({ ...localStorage });
    const done = copilot.ask('a');
    http.expectOne(url).flush({ text: 'segredo do altar' });
    await done;
    expect(JSON.stringify({ ...localStorage })).toBe(before);
    expect(JSON.stringify({ ...sessionStorage })).not.toContain('segredo do altar');
  });

  it('limpar tira a resposta e o erro', async () => {
    const { http, copilot } = setup();
    const done = copilot.ask('a');
    http.expectOne(url).flush({ text: 'x' });
    await done;
    copilot.clear();
    expect([copilot.answer(), copilot.asked(), copilot.error()]).toEqual(['', '', '']);
  });
});
