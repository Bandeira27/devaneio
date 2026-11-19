import { TestBed } from '@angular/core/testing';
import type { LlmSettingsView } from '@contract/api_responses';
import { setup } from '../../testing/setup';
import { isRemote, parseTimeout } from './llm-settings.store';

const KEY = 'sk-CANARIO-9f3a7c1d';
const NOT_FOUND = { error: { code: 'not_found', message: 'x' } };
const NONE: LlmSettingsView = {
  source: 'none',
  disabled: false,
  base_url: null,
  model: null,
  timeout: null,
  key_set: false,
  description: null,
};
const SAVED: LlmSettingsView = {
  source: 'screen',
  disabled: false,
  base_url: 'http://localhost:11434/v1',
  model: 'qwen3',
  timeout: 120,
  key_set: true,
  description: 'qwen3 em localhost:11434',
};

type App = Awaited<ReturnType<typeof setup>>;

/** Abre `/configuracao` e responde à leitura da configuração. */
async function open(view: LlmSettingsView | null = NONE) {
  const app = await setup('/configuracao');
  const read = app.http.expectOne('/editor/settings/llm');
  if (view === null) {
    read.flush(NOT_FOUND, { status: 404, statusText: 'x' });
  } else {
    read.flush(view);
  }
  await app.settle();
  return app;
}

function type(app: App, label: string, value: string): void {
  const field = Array.from(app.root().querySelectorAll('dv-field')).find((f) =>
    f.textContent?.includes(label),
  );
  const input = field?.querySelector('input');
  if (!(input instanceof HTMLInputElement)) {
    throw new Error(`campo não achado: ${label}`);
  }
  input.value = value;
  input.dispatchEvent(new Event('input'));
}

function submit(app: App): void {
  (app.root().querySelector('form') as HTMLFormElement).dispatchEvent(
    new Event('submit', { cancelable: true }),
  );
}

function fill(app: App, over: { key?: string; url?: string } = {}): void {
  type(app, 'Endereço do servidor', over.url ?? 'http://localhost:11434/v1');
  type(app, 'Modelo', 'qwen3');
  type(app, 'Tempo limite', '120');
  if (over.key !== undefined) {
    type(app, 'Chave de acesso', over.key);
  }
}

describe('Configuração do LLM', () => {
  it('sem LLM, avisa que o jogo roda só com o motor e não mostra chave', async () => {
    const app = await open();
    expect(app.root().querySelector('h1')?.textContent).toContain('Configuração');
    expect(app.root().textContent).toContain('Nenhum mestre de IA configurado');
    expect(app.root().textContent).toContain('Sem chave');
  });

  it('de fora da máquina do servidor diz que só abre em localhost', async () => {
    const app = await open(null);
    expect(app.root().textContent).toContain('só abre no computador onde o servidor roda');
    expect(app.root().querySelector('form')).toBeNull();
  });

  it('avisa quando o LLM vem do ambiente e quando o servidor foi iniciado com --sem-llm', async () => {
    const env = await open({
      ...NONE,
      source: 'environment',
      description: 'm em ambiente.example',
    });
    expect(env.root().textContent).toContain('(variáveis de ambiente): m em ambiente.example');
  });

  it('avisa do --sem-llm', async () => {
    const app = await open({ ...NONE, disabled: true });
    expect(app.root().textContent).toContain('--sem-llm');
  });

  it('salva, manda a chave só no envio e nunca a mostra de volta', async () => {
    const app = await open();
    fill(app, { key: KEY });
    await app.settle(); // a tela já mostrou o que foi digitado, como acontece a cada tecla
    submit(app);
    const put = app.http.expectOne('/editor/settings/llm');
    expect(put.request.method).toBe('PUT');
    expect(put.request.body).toEqual({
      base_url: 'http://localhost:11434/v1',
      model: 'qwen3',
      timeout: 120,
      api_key: KEY,
    });
    put.flush(SAVED);
    await app.settle();
    expect(app.root().textContent).toContain('Configuração guardada');
    expect(app.root().textContent).toContain('Chave guardada');
    expect(app.root().innerHTML).not.toContain(KEY);
    const password = app.root().querySelector('input[type="password"]') as HTMLInputElement;
    expect(password.value).toBe('');
  });

  it('sem chave digitada, o envio não leva o campo da chave (mantém a atual)', async () => {
    const app = await open(SAVED);
    submit(app);
    const put = app.http.expectOne('/editor/settings/llm');
    expect(put.request.body).not.toHaveProperty('api_key');
    put.flush(SAVED);
    await app.settle();
  });

  it('confere o endereço antes de enviar: sem usuário e senha, sem esquema estranho', async () => {
    const app = await open();
    fill(app, { url: 'http://user:senha@host/v1' });
    submit(app);
    await app.settle();
    app.http.expectNone('/editor/settings/llm');
    expect(app.root().textContent).toContain('não pode ter usuário e senha');

    type(app, 'Endereço do servidor', 'ftp://host');
    submit(app);
    await app.settle();
    expect(app.root().textContent).toContain('precisa começar com http://');
  });

  it('o tempo precisa ser um número razoável', async () => {
    const app = await open();
    fill(app);
    type(app, 'Tempo limite', 'abc');
    submit(app);
    await app.settle();
    app.http.expectNone('/editor/settings/llm');
    expect(app.root().textContent).toContain('Use um número de 1 a 600');
  });

  it('mostra o erro do servidor sem inventar outro texto', async () => {
    const app = await open();
    fill(app);
    submit(app);
    app.http
      .expectOne('/editor/settings/llm')
      .flush(
        { error: { code: 'invalid_settings', message: 'o endereço não pode ter parâmetros' } },
        { status: 422, statusText: 'x' },
      );
    await app.settle();
    expect(app.root().querySelector('[role="alert"]')?.textContent).toContain(
      'não pode ter parâmetros',
    );
  });

  it('"Salvar e testar" guarda e depois testa, mostrando a frase do servidor', async () => {
    const app = await open();
    fill(app, { key: KEY });
    const test = Array.from(app.root().querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Salvar e testar'),
    ) as HTMLButtonElement;
    test.click();
    app.http.expectOne('/editor/settings/llm').flush(SAVED);
    await app.settle();
    const probe = app.http.expectOne('/editor/settings/llm/test');
    expect(probe.request.method).toBe('POST');
    probe.flush({ ok: false, message: 'O servidor recusou a chave (HTTP 401).' });
    await app.settle();
    expect(app.root().querySelector('[role="alert"]')?.textContent).toContain('HTTP 401');
  });

  it('a tela inicial oferece a configuração só com o editor ligado', async () => {
    const off = await setup('/');
    off.http.expectOne('/campaigns').flush([]);
    off.http.expectOne('/editor/campaigns').flush(NOT_FOUND, { status: 404, statusText: 'x' });
    await off.settle();
    expect(off.root().querySelector('a[href="/configuracao"]')).toBeNull();

    TestBed.resetTestingModule();
    const on = await setup('/');
    on.http.expectOne('/campaigns').flush([]);
    on.http.expectOne('/editor/campaigns').flush([]);
    await on.settle();
    expect(on.root().querySelector('a[href="/configuracao"]')?.textContent).toContain(
      'Configurar o mestre de IA',
    );
  });

  it('o formulário não usa a validação do navegador, que engoliria as mensagens daqui', async () => {
    const app = await open();
    expect(app.root().querySelector('form')?.hasAttribute('novalidate')).toBe(true);
    expect(app.root().querySelector('input[inputmode="url"]')?.getAttribute('type')).toBe('text');
  });

  it('erro de validação leva o foco ao primeiro campo com erro', async () => {
    const app = await open();
    fill(app, { url: 'ftp://host' });
    await app.settle();
    submit(app);
    await app.settle();
    const active = document.activeElement as HTMLElement | null;
    expect(active?.getAttribute('aria-invalid')).toBe('true');
    expect(active?.closest('dv-field')?.textContent).toContain('Endereço do servidor');
  });

  it('o tempo aceita vírgula decimal e recusa notação científica', async () => {
    expect(parseTimeout('1,5')).toBe(1.5);
    expect(parseTimeout(' 90 ')).toBe(90);
    expect(parseTimeout('')).toBe(60);
    expect(parseTimeout('1e2')).toBeNull();
    expect(parseTimeout('abc')).toBeNull();
  });

  it('avisa quando o endereço não é deste computador, e só então', async () => {
    const app = await open();
    type(app, 'Endereço do servidor', 'http://localhost:11434/v1');
    await app.settle();
    expect(app.root().textContent).not.toContain('não é deste computador');
    type(app, 'Endereço do servidor', 'https://api.exemplo.com/v1');
    await app.settle();
    expect(app.root().textContent).toContain('não é deste computador');
    expect(isRemote('http://127.0.0.1:8080')).toBe(false);
    expect(isRemote('http://[::1]:8080')).toBe(false);
    expect(isRemote('lixo')).toBe(false);
  });

  it('com chave guardada, a dica diz como mantê-la ou trocá-la', async () => {
    const app = await open(SAVED);
    expect(app.root().textContent).toContain('Já há uma chave guardada');
    expect(app.root().textContent).toContain('Chave guardada');
    expect(app.root().textContent).toContain('Em uso: qwen3 em localhost:11434');
  });

  it('o aviso de privacidade vem antes do formulário', async () => {
    const app = await open();
    const text = app.root().textContent ?? '';
    expect(text.indexOf('Para onde vão os dados')).toBeLessThan(
      text.indexOf('Endereço do servidor'),
    );
  });

  it('o teste com sucesso mostra um só aviso, com o que foi guardado e a resposta', async () => {
    const app = await open();
    fill(app);
    (
      Array.from(app.root().querySelectorAll('button')).find((b) =>
        b.textContent?.includes('Salvar e testar'),
      ) as HTMLButtonElement
    ).click();
    app.http.expectOne('/editor/settings/llm').flush(SAVED);
    await app.settle();
    expect(app.root().textContent).toContain('Testando a conexão');
    app.http
      .expectOne('/editor/settings/llm/test')
      .flush({ ok: true, message: 'O servidor respondeu.' });
    await app.settle();
    const notices = app.root().querySelectorAll('dv-notice');
    expect(notices).toHaveLength(1);
    expect(notices[0]?.textContent).toContain('Configuração guardada. O servidor respondeu.');
  });

  it('enquanto um envio está em andamento, os outros botões esperam', async () => {
    const app = await open();
    fill(app);
    submit(app);
    await app.settle();
    const buttons = Array.from(app.root().querySelectorAll('button[dvButton], button.dv-button'));
    expect(buttons.length).toBeGreaterThan(0);
    for (const button of buttons) {
      expect(button.getAttribute('aria-disabled')).toBe('true');
    }
    app.http.expectOne('/editor/settings/llm').flush(SAVED);
    await app.settle();
  });

  it('falha ao ler a configuração oferece tentar de novo', async () => {
    const app = await setup('/configuracao');
    app.http
      .expectOne('/editor/settings/llm')
      .flush({ error: { code: 'internal', message: 'x' } }, { status: 500, statusText: 'x' });
    await app.settle();
    const retry = Array.from(app.root().querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Tentar de novo'),
    ) as HTMLButtonElement;
    retry.click();
    app.http.expectOne('/editor/settings/llm').flush(NONE);
    await app.settle();
    expect(app.root().querySelector('form')).not.toBeNull();
  });

  it('no estado indisponível há uma só saída para o início', async () => {
    const app = await open(null);
    expect(
      Array.from(app.root().querySelectorAll('a')).filter((a) =>
        a.textContent?.includes('Voltar ao início'),
      ),
    ).toHaveLength(1);
  });
});
