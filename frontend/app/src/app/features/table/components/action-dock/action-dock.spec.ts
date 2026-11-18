import type { EventsView, TableView } from '@contract/api_responses';
import { TABLE_ID, campaignView, rulesView, tableView } from '../../../../testing/fixtures';
import { setup } from '../../../../testing/setup';

const eventsView = (revision: number): EventsView => ({
  revision,
  events: [],
  talk: [],
  talk_seq: 0,
});
const commandResult = (over: object = {}) => ({
  revision: 4,
  events: [],
  text: '',
  status: 'active',
  turn_ended: false,
  ...over,
});

function table(over: Partial<TableView> = {}): TableView {
  const view = tableView({
    players: [
      { id: 'p1', name: 'Ana', role: 'host', character_ids: [] },
      { id: 'p2', name: 'Bia', role: 'player', character_ids: ['bia'] },
    ],
    role: 'host', // Comando é só do anfitrião; os testes de jogador comum passam `role: 'player'`
    ...over,
  });
  view.state = {
    ...view.state,
    characters: {
      bia: {
        id: 'bia',
        name: 'Bia',
        attributes: { FOR: 3 },
        hp: 8,
        max_hp: 10,
        inventory: [],
      },
    },
    npcs: {
      ferreiro: { id: 'ferreiro', name: 'ferreiro', hp: 5, max_hp: 5, alive: true },
    } as never,
  };
  return view;
}

async function open(view: TableView = table()) {
  const app = await setup(`/mesa/${TABLE_ID}`);
  app.session.save(TABLE_ID, {
    token: 'tk',
    playerId: 'p2',
    role: 'player',
    title: 'x',
    savedAt: 1,
  });
  app.http.expectOne(`/tables/${TABLE_ID}`).flush(view);
  app.http.expectOne(`/tables/${TABLE_ID}/rules`).flush(rulesView());
  app.http.expectOne(`/tables/${TABLE_ID}/campaign`).flush(campaignView());
  await app.settle();
  app.http
    .expectOne((r) => r.url === `/tables/${TABLE_ID}/events` && r.params.get('wait') === '0')
    .flush(eventsView(3));
  await app.settle();
  const sheet = (): HTMLElement | null => document.querySelector('.dv-sheet');
  const press = async (label: string): Promise<void> => {
    const button = Array.from(app.root().querySelectorAll('dv-action-dock button')).find(
      (b) => b.textContent?.trim() === label,
    ) as HTMLButtonElement;
    button.click();
    await app.settle();
  };
  const inSheet = async (selector: string): Promise<void> => {
    (sheet()?.querySelector(selector) as HTMLElement).click();
    await app.settle();
  };
  const typeIn = async (selector: string, value: string): Promise<void> => {
    const input = sheet()?.querySelector(selector) as HTMLInputElement | HTMLTextAreaElement;
    input.value = value;
    input.dispatchEvent(new Event('input'));
    await app.settle();
  };
  const commandRequest = () => app.http.expectOne(`/tables/${TABLE_ID}/commands`);
  return { ...app, sheet, press, inSheet, typeIn, commandRequest };
}

/** Depois de agir, a mesa relê tudo: responde as três leituras para limpar as pendências. */
async function answerReread(
  app: Awaited<ReturnType<typeof open>>,
  view: TableView = table({ revision: 4 }),
) {
  await app.settle();
  app.http.expectOne(`/tables/${TABLE_ID}`).flush(view);
  app.http.expectOne(`/tables/${TABLE_ID}/campaign`).flush(campaignView());
  await app.settle();
}

describe('Ações da mesa', () => {
  afterEach(() => {
    document.querySelectorAll('.cdk-overlay-container').forEach((el) => {
      el.replaceChildren();
    });
  });

  it('Ir abre as saídas e manda "ir <id>" com a revisão atual', async () => {
    const app = await open();
    await app.press('Ir');
    expect(app.sheet()?.textContent).toContain('Floresta');
    expect(app.sheet()?.textContent).toContain('Para onde ir?');
    app.http.expectNone(`/tables/${TABLE_ID}/commands`); // abrir a folha não envia nada
    expect(app.sheet()?.textContent).toContain('Gasta a sua ação');
    await app.inSheet('.dv-sheet__foot .dv-button--primary');
    const request = app.commandRequest();
    expect(request.request.body).toEqual({ line: 'ir floresta', revision: 3 });
    expect(request.request.headers.get('Authorization')).toBe('Bearer tk');
    request.flush(commandResult());
    await answerReread(app);
    expect(app.sheet()).toBeNull();
  });

  it('Testar mostra a fórmula e manda a linha montada', async () => {
    const app = await open();
    await app.press('Testar');
    expect(app.sheet()?.textContent).toContain('Rola 2d6 + Força');
    (app.sheet()?.querySelector('form') as HTMLFormElement).dispatchEvent(
      new Event('submit', { cancelable: true }),
    );
    await app.settle();
    const request = app.commandRequest();
    expect(request.request.body).toEqual({ line: 'testar lutar normal', revision: 3 });
    request.flush(commandResult());
    await answerReread(app);
  });

  it('Atacar oferece alvo e arma e manda a linha de ataque', async () => {
    const app = await open();
    await app.press('Atacar');
    expect(app.sheet()?.textContent).toContain('ferreiro');
    expect(app.sheet()?.textContent).toContain('Punhos');
    (app.sheet()?.querySelector('form') as HTMLFormElement).dispatchEvent(
      new Event('submit', { cancelable: true }),
    );
    await app.settle();
    app.http.expectNone(`/tables/${TABLE_ID}/commands`);
    expect(app.sheet()?.textContent).toContain('Atacar ferreiro com Punhos');
    await app.inSheet('.dv-sheet__foot .dv-button--primary');
    const request = app.commandRequest();
    expect((request.request.body as { line: string }).line).toBe('atacar punhos ferreiro');
    request.flush(commandResult());
    await answerReread(app);
  });

  it('Comando é só do anfitrião: o jogador comum não o vê', async () => {
    const app = await open(table({ role: 'player' }));
    const labels = Array.from(app.root().querySelectorAll('dv-action-dock button')).map((b) =>
      b.textContent?.trim(),
    );
    expect(labels).not.toContain('Comando');
    expect(labels).toContain('Ficha');
  });

  it('sem mestre de IA, Testar é o botão em destaque', async () => {
    const semIa = await open();
    const primary = (app: typeof semIa) =>
      Array.from(app.root().querySelectorAll('dv-action-dock .dv-button--primary')).map((b) =>
        b.textContent?.trim(),
      );
    expect(primary(semIa)).toEqual(['Testar']);
  });

  it('sem personagem, Ficha fica bloqueada com o motivo ligado', async () => {
    const app = await open(
      table({ players: [{ id: 'p1', name: 'Ana', role: 'host', character_ids: [] }] }),
    );
    const ficha = Array.from(app.root().querySelectorAll('dv-action-dock button')).find(
      (b) => b.textContent?.trim() === 'Ficha',
    );
    expect(ficha?.getAttribute('aria-disabled')).toBe('true');
    expect(ficha?.getAttribute('aria-describedby')).toBe('no-character');
  });

  it('Ficha mostra atributos e inventário sem chamar o servidor', async () => {
    const app = await open();
    await app.press('Ficha');
    expect(app.sheet()?.textContent).toContain('Bia');
    expect(app.sheet()?.textContent).toContain('Força');
    expect(app.sheet()?.textContent).toContain('vazio');
    app.http.expectNone(`/tables/${TABLE_ID}/commands`);
  });

  it('Comando manda a linha crua e mostra a resposta de texto', async () => {
    const app = await open();
    await app.press('Comando');
    await app.typeIn('input', 'olhar');
    (app.sheet()?.querySelector('form') as HTMLFormElement).dispatchEvent(
      new Event('submit', { cancelable: true }),
    );
    await app.settle();
    app.commandRequest().flush(commandResult({ text: 'Você vê uma vila.' }));
    await answerReread(app);
    expect(app.root().querySelector('dv-action-dock')?.textContent).toContain('Você vê uma vila.');
  });

  it('com a mesa adiante (stale_revision) relê e tenta de novo uma vez', async () => {
    const app = await open();
    await app.press('Comando');
    await app.typeIn('input', 'olhar');
    (app.sheet()?.querySelector('form') as HTMLFormElement).dispatchEvent(
      new Event('submit', { cancelable: true }),
    );
    await app.settle();
    app
      .commandRequest()
      .flush(
        { error: { code: 'stale_revision', message: 'A mesa mudou.' } },
        { status: 409, statusText: 'Conflict' },
      );
    await app.settle();
    app.http.expectOne(`/tables/${TABLE_ID}`).flush(table({ revision: 7 }));
    app.http.expectOne(`/tables/${TABLE_ID}/campaign`).flush(campaignView());
    await app.settle();
    const retry = app.commandRequest();
    expect((retry.request.body as { revision: number }).revision).toBe(7);
    retry.flush(commandResult({ text: 'ok' }));
    await answerReread(app, table({ revision: 8 }));
    expect(app.root().querySelector('dv-action-dock dv-notice[kind="error"]')).toBeNull();
  });

  it('refresh pedido com outra leitura em voo dispara uma leitura nova depois do pedido', async () => {
    const app = await open();
    await app.press('Comando');
    await app.typeIn('input', 'olhar');
    (app.sheet()?.querySelector('form') as HTMLFormElement).dispatchEvent(
      new Event('submit', { cancelable: true }),
    );
    await app.settle();
    app.commandRequest().flush(commandResult({ text: 'ok' }));
    await app.settle();
    // a ação disparou a primeira releitura; enquanto ela voa, o long-poll traz a revisão seguinte
    const first = app.http.expectOne(`/tables/${TABLE_ID}`);
    const firstCampaign = app.http.expectOne(`/tables/${TABLE_ID}/campaign`);
    app.http
      .expectOne((r) => r.url === `/tables/${TABLE_ID}/events` && r.params.get('wait') === '20')
      .flush({ revision: 9, events: [], talk: [], talk_seq: 0 });
    await app.settle();
    first.flush(table({ revision: 8 }));
    firstCampaign.flush(campaignView());
    await app.settle();
    const second = app.http.expectOne(`/tables/${TABLE_ID}`);
    app.http.expectOne(`/tables/${TABLE_ID}/campaign`).flush(campaignView());
    second.flush(table({ revision: 9 }));
    await app.settle();
    expect(app.root().querySelector('dv-table-page, .table')).not.toBeNull();
  });

  it('um erro do servidor aparece como texto e não trava os botões', async () => {
    const app = await open();
    await app.press('Comando');
    await app.typeIn('input', 'dança');
    (app.sheet()?.querySelector('form') as HTMLFormElement).dispatchEvent(
      new Event('submit', { cancelable: true }),
    );
    await app.settle();
    app
      .commandRequest()
      .flush(
        { error: { code: 'bad_command', message: 'Comando desconhecido: <b>dança</b>' } },
        { status: 422, statusText: 'Unprocessable' },
      );
    await app.settle();
    const dock = app.root().querySelector('dv-action-dock') as HTMLElement;
    expect(dock.textContent).toContain('Comando desconhecido: <b>dança</b>');
    expect(dock.querySelector('b')).toBeNull();
    expect(dock.querySelector<HTMLButtonElement>('button')?.disabled).toBe(false);
  });

  it('já agiu neste turno: bloqueia as ações com o motivo ligado a cada botão, mas deixa Ficha e Comando', async () => {
    const app = await open(table({ acted: { bia: 0 } }));
    const dock = app.root().querySelector('dv-action-dock') as HTMLElement;
    const button = (label: string) =>
      Array.from(dock.querySelectorAll('button')).find((b) => b.textContent?.trim() === label);
    for (const label of ['Ir', 'Testar', 'Atacar']) {
      expect(button(label)?.getAttribute('aria-disabled'), label).toBe('true');
      expect(button(label)?.disabled, label).toBe(false); // continua no foco: o motivo se lê
      expect(button(label)?.getAttribute('aria-describedby'), label).toBe('dock-reason');
    }
    expect(button('Ficha')?.getAttribute('aria-disabled')).toBeNull();
    expect(button('Comando')?.getAttribute('aria-disabled')).toBeNull();
    expect(dock.querySelector('#dock-reason')?.textContent?.trim()).not.toBe('');
  });

  it('um botão bloqueado não abre a folha', async () => {
    const app = await open(table({ acted: { bia: 0 } }));
    await app.press('Ir');
    expect(app.sheet()).toBeNull();
  });

  it('Falar só existe com o LLM ligado e manda o texto livre', async () => {
    const without = await open();
    expect(
      Array.from(without.root().querySelectorAll('dv-action-dock button')).some(
        (b) => b.textContent?.trim() === 'Falar',
      ),
    ).toBe(false);
  });

  it('Falar com o LLM ligado manda o texto para /say e mostra a resposta do mestre', async () => {
    const app = await open(
      table({ llm: { enabled: true, description: 'm', notice: 'n', secrets: false } }),
    );
    await app.press('Falar');
    await app.typeIn('textarea', 'Olho o altar.');
    (app.sheet()?.querySelector('form') as HTMLFormElement).dispatchEvent(
      new Event('submit', { cancelable: true }),
    );
    await app.settle();
    const request = app.http.expectOne(`/tables/${TABLE_ID}/say`);
    expect(request.request.body).toEqual({ text: 'Olho o altar.', revision: 3 });
    expect(app.root().querySelector('dv-action-dock')?.textContent).toContain('pensando');
    request.flush({ ...commandResult(), say: 'O altar range.', commands: [] });
    await answerReread(app);
    expect(app.root().querySelector('dv-action-dock')?.textContent).toContain('O altar range.');
  });
});
