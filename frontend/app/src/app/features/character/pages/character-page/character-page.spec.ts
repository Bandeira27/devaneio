import type { TableView } from '@contract/api_responses';
import { campaignView, rulesView, tableView, TABLE_ID } from '../../../../testing/fixtures';
import { setup } from '../../../../testing/setup';

describe('Personagem', () => {
  const url = `/mesa/${TABLE_ID}/personagem`;

  async function open(table: TableView = tableView(), npcs = ['ferreiro']) {
    const app = await setup(url);
    app.session.save(TABLE_ID, {
      token: 'tk',
      playerId: 'p2',
      role: 'player',
      title: 'x',
      savedAt: 1,
    });
    app.http.expectOne(`/tables/${TABLE_ID}`).flush(table);
    app.http.expectOne(`/tables/${TABLE_ID}/rules`).flush(rulesView());
    app.http.expectOne(`/tables/${TABLE_ID}/campaign`).flush(campaignView(npcs));
    await app.settle();
    return app;
  }

  const line = (http: Awaited<ReturnType<typeof open>>['http']) =>
    http.expectOne(`/tables/${TABLE_ID}/commands`);

  it('mostra um stepper por atributo, no valor padrão e com a descrição', async () => {
    const { root } = await open();
    const steppers = Array.from(root().querySelectorAll('dv-stepper'));
    expect(steppers.map((s) => s.querySelector('.stepper__label')?.textContent)).toEqual([
      'Força',
      'Agilidade',
    ]);
    expect(steppers.map((s) => s.querySelector('output')?.textContent)).toEqual(['2', '2']);
    expect(steppers[0]?.querySelector('.stepper__hint')?.textContent).toBe('Descrição de Força');
  });

  it('manda a linha entrar com o id em slug, o nome e os atributos, e vai para a mesa', async () => {
    const { http, root, type, click, submit, settle, router } = await open();
    await type('input[type="text"]', 'João da Silva');
    await click('[aria-label="Aumentar Força"]');
    await click('[aria-label="Aumentar Força"]');
    await click('[aria-label="Diminuir Agilidade"]');
    expect(root().querySelectorAll('output')[0]?.textContent).toBe('4');
    await submit();
    const request = line(http);
    expect(request.request.body).toEqual({
      line: 'entrar joao-da-silva "João da Silva" FOR=4 AGI=1',
      revision: 3,
    });
    expect(request.request.headers.get('Authorization')).toBe('Bearer tk');
    request.flush({ revision: 4, events: [], text: '', status: 'active', turn_ended: false });
    await settle();
    await vi.waitFor(() => expect(router.url).toBe(`/mesa/${TABLE_ID}`));
    http.match(() => true);
  });

  it('o id ganha sufixo quando já existe outro personagem ou um NPC com ele', async () => {
    const table = tableView();
    table.state = {
      ...table.state,
      characters: {
        aria: { id: 'aria', name: 'Aria', attributes: {}, hp: 1, max_hp: 1, inventory: [] },
      },
    };
    const { http, type, submit } = await open(table, ['ferreiro']);
    await type('input[type="text"]', 'Aria');
    await submit();
    expect((line(http).request.body as { line: string }).line.startsWith('entrar aria-2 ')).toBe(
      true,
    );
  });

  it('um nome igual ao de um NPC da campanha também ganha sufixo', async () => {
    const { http, type, submit } = await open(tableView(), ['ferreiro']);
    await type('input[type="text"]', 'Ferreiro');
    await submit();
    expect(
      (line(http).request.body as { line: string }).line.startsWith('entrar ferreiro-2 '),
    ).toBe(true);
  });

  it('exige o nome e não chama a API sem ele', async () => {
    const { root, http, type, submit } = await open();
    await type('input[type="text"]', '');
    await submit();
    expect(root().textContent).toContain('Dê um nome ao personagem.');
    http.expectNone(`/tables/${TABLE_ID}/commands`);
  });

  it('o personagem nasce com o nome de quem joga, e o erro some ao digitar', async () => {
    const { root, type, submit } = await open();
    const field = () => root().querySelector('input[type="text"]') as HTMLInputElement;
    expect(field().value).toBe('Bia');
    await type('input[type="text"]', '');
    await submit();
    expect(root().textContent).toContain('Dê um nome ao personagem.');
    await type('input[type="text"]', 'B');
    expect(root().textContent).not.toContain('Dê um nome ao personagem.');
  });

  it('"Restaurar padrão" só vale depois de mexer nos atributos', async () => {
    const { root, click } = await open();
    const restore = () => root().querySelector('button[type="button"]:not([aria-label])');
    expect(restore()?.getAttribute('aria-disabled')).toBe('true');
    await click('[aria-label="Aumentar Força"]');
    expect(restore()?.getAttribute('aria-disabled')).toBeNull();
  });

  it('"Restaurar padrão" desfaz o que foi mexido', async () => {
    const { root, click } = await open();
    await click('[aria-label="Aumentar Força"]');
    expect(root().querySelectorAll('output')[0]?.textContent).toBe('3');
    await click('button[type="button"]:not([aria-label])');
    expect(root().querySelectorAll('output')[0]?.textContent).toBe('2');
  });

  it('se a mesa andou (stale_revision) relê a revisão e tenta de novo, uma vez', async () => {
    const { http, type, submit, settle, router } = await open();
    await type('input[type="text"]', 'Ana');
    await submit();
    line(http).flush(
      { error: { code: 'stale_revision', message: 'a mesa mudou' } },
      { status: 409, statusText: 'Conflict' },
    );
    await settle();
    http.expectOne(`/tables/${TABLE_ID}`).flush(tableView({ revision: 9 }));
    await settle();
    const retry = line(http);
    expect((retry.request.body as { revision: number }).revision).toBe(9);
    retry.flush({ revision: 10, events: [], text: '', status: 'active', turn_ended: false });
    await settle();
    await vi.waitFor(() => expect(router.url).toBe(`/mesa/${TABLE_ID}`));
    http.match(() => true);
  });

  it('um erro do motor (command_refused) aparece e o formulário continua', async () => {
    const { root, http, type, submit, settle } = await open();
    await type('input[type="text"]', 'Ana');
    await submit();
    line(http).flush(
      { error: { code: 'command_refused', message: "'ana' já existe" } },
      { status: 422, statusText: 'x' },
    );
    await settle();
    expect(root().querySelector('[role="alert"]')?.textContent).toContain("'ana' já existe");
    expect(root().querySelector('form')).not.toBeNull();
  });

  it('mostra o aviso do LLM da mesa quando ele está ligado', async () => {
    const table = tableView({
      llm: {
        enabled: true,
        description: 'm em h',
        notice: 'O texto vai ao servidor de LLM m em h.',
        secrets: false,
      },
    });
    const { root } = await open(table);
    expect(root().textContent).toContain('O que o mestre de IA recebe');
    expect(root().textContent).toContain('O texto vai ao servidor de LLM m em h.');
  });

  it('sem LLM não há aviso', async () => {
    const { root } = await open();
    expect(root().textContent).not.toContain('mestre de IA');
  });

  it('quem já tem personagem vai direto para a mesa', async () => {
    const table = tableView({
      players: [{ id: 'p2', name: 'Bia', role: 'player', character_ids: ['bia'] }],
    });
    const app = await setup(url);
    app.session.save(TABLE_ID, {
      token: 'tk',
      playerId: 'p2',
      role: 'player',
      title: 'x',
      savedAt: 1,
    });
    app.http.expectOne(`/tables/${TABLE_ID}`).flush(table);
    app.http.expectOne(`/tables/${TABLE_ID}/rules`).flush(rulesView());
    app.http.expectOne(`/tables/${TABLE_ID}/campaign`).flush(campaignView());
    await vi.waitFor(() => expect(app.router.url).toBe(`/mesa/${TABLE_ID}`));
  });

  it('o anfitrião também cria personagem e pode pular', async () => {
    const table = tableView({ role: 'host', you: 'p1' });
    const { root } = await open(table);
    expect(root().textContent).toContain('Como anfitrião você também pode jogar.');
    expect(Array.from(root().querySelectorAll('a')).map((a) => a.getAttribute('href'))).toContain(
      `/mesa/${TABLE_ID}`,
    );
  });

  it('token inválido ou mesa que sumiu: mostra o erro e esquece a sessão', async () => {
    const app = await setup(url);
    app.session.save(TABLE_ID, {
      token: 'velho',
      playerId: 'p2',
      role: 'player',
      title: 'x',
      savedAt: 1,
    });
    const reject = { error: { code: 'unauthorized', message: 'token inválido' } };
    app.http.expectOne(`/tables/${TABLE_ID}`).flush(reject, { status: 401, statusText: 'x' });
    app.http.match(() => true).forEach((r) => r.flush(reject, { status: 401, statusText: 'x' }));
    await app.settle();
    expect(app.root().querySelector('[role="alert"]')?.textContent).toContain(
      'sessão nesta mesa expirou',
    );
    expect(app.session.get(TABLE_ID)).toBeNull();
    expect(app.root().querySelector('a[href="/"]')).not.toBeNull();
  });
});
