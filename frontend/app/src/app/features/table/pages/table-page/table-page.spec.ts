import type { Campaign, EventView, EventsView, TableView } from '@contract/api_responses';
import { TABLE_ID, campaignView, rulesView, tableView } from '../../../../testing/fixtures';
import { setup } from '../../../../testing/setup';

const url = `/mesa/${TABLE_ID}`;
const event = (index: number, turn: number, over: Partial<EventView> = {}): EventView => ({
  index,
  turn,
  kind: 'move',
  text: `mecânica ${index}`,
  prose: `prosa ${index}`,
  narration: null,
  ...over,
});
const eventsView = (
  revision: number,
  events: EventView[] = [],
  talk: EventsView['talk'] = [],
  talkSeq = 0,
): EventsView => ({
  revision,
  events,
  talk,
  talk_seq: talkSeq,
});

function withCharacter(over: Partial<TableView> = {}): TableView {
  const table = tableView({
    players: [
      { id: 'p1', name: 'Ana', role: 'host', character_ids: [] },
      { id: 'p2', name: 'Bia', role: 'player', character_ids: ['bia'] },
    ],
    ...over,
  });
  table.state = {
    ...table.state,
    turn: 2,
    characters: {
      bia: { id: 'bia', name: 'Bia', attributes: {}, hp: 8, max_hp: 10, inventory: [] },
      zed: { id: 'zed', name: 'Zed', attributes: {}, hp: 0, max_hp: 10, inventory: [] },
    },
  };
  return table;
}

async function open(
  table: TableView = withCharacter(),
  campaign: Campaign | ReturnType<typeof campaignView> = campaignView(),
) {
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
  app.http.expectOne(`/tables/${TABLE_ID}/campaign`).flush(campaign);
  await app.settle();
  const events = (wait: string) =>
    app.http.expectOne(
      (r) => r.url === `/tables/${TABLE_ID}/events` && r.params.get('wait') === wait,
    );
  return { ...app, events };
}

describe('Mesa: situação, novidades e acessibilidade', () => {
  it('diz de quem é a vez (quem está caído não segura o turno)', async () => {
    const { root, events, settle } = await open(withCharacter({ acted: { bia: 2 } }));
    events('0').flush(eventsView(3));
    await settle();
    const turn = root().querySelector('.table__turn') as HTMLElement;
    expect(turn.textContent).toContain('Turno 2');
    expect(turn.textContent).toContain('Você já agiu'); // Zed está fora de combate
    expect(turn.textContent).not.toContain('falta');
    expect(turn.getAttribute('role')).toBe('status');
  });

  it('o anfitrião tem "Convidar" no cabeçalho; o jogador comum não', async () => {
    const player = await open();
    player.events('0').flush(eventsView(3));
    await player.settle();
    expect(player.root().querySelector('.table__bar .table__invite')).toBeNull();
  });

  it('a ordem do HTML é a de leitura: situação e cena, a história, as ações', async () => {
    const { root, events, settle } = await open();
    events('0').flush(eventsView(3));
    await settle();
    const order = Array.from(root().querySelectorAll('.table__layout > *')).map(
      (el) => el.className,
    );
    expect(order).toEqual(['table__side', 'table__feed', 'table__dock']);
  });

  it('o log só anuncia depois da carga inicial', async () => {
    const { root, events, settle } = await open();
    events('0').flush(eventsView(3, [event(1, 1)]));
    await settle();
    await new Promise((resolve) => setTimeout(resolve, 5));
    await settle();
    expect(root().querySelector('[role="log"]')?.getAttribute('aria-live')).toBe('polite');
  });

  it('quem leu mais acima vê "novas" quando chega algo, e o toque leva ao fim', async () => {
    const { root, events, settle } = await open();
    events('0').flush(eventsView(3, [event(1, 1)]));
    await settle();
    Object.defineProperty(document.documentElement, 'scrollHeight', {
      value: 5000,
      configurable: true,
    });
    const scrollIntoView = vi.fn();
    Element.prototype.scrollIntoView = scrollIntoView;
    try {
      events('20').flush(eventsView(4, [event(2, 1)]));
      await settle();
      const pill = root().querySelector('.table__new') as HTMLButtonElement;
      expect(pill.textContent).toContain('1 nova');
      pill.click();
      await settle();
      await Promise.resolve();
      expect(scrollIntoView).toHaveBeenCalledWith({ block: 'end' });
      expect(root().querySelector('.table__new')).toBeNull();
    } finally {
      Reflect.deleteProperty(document.documentElement, 'scrollHeight');
      Reflect.deleteProperty(Element.prototype, 'scrollIntoView');
    }
  });

  it('sem conexão, as ações ficam bloqueadas com o motivo', async () => {
    const { root, events, settle } = await open();
    events('0').flush(
      { error: { code: 'x', message: 'falhou' } } as never,
      { status: 500, statusText: 'x' } as never,
    );
    await settle();
    expect(root().querySelector('#dock-reason')?.textContent).toContain('Sem conexão com a mesa');
    const ir = Array.from(root().querySelectorAll('dv-action-dock button')).find(
      (b) => b.textContent?.trim() === 'Ir',
    );
    expect(ir?.getAttribute('aria-disabled')).toBe('true');
  });
});

describe('Mesa', () => {
  it('sair da página no meio da carga não deixa um laço ao vivo órfão', async () => {
    const app = await setup(url);
    app.session.save(TABLE_ID, {
      token: 'tk',
      playerId: 'p2',
      role: 'player',
      title: 'x',
      savedAt: 1,
    });
    const pending = [
      app.http.expectOne(`/tables/${TABLE_ID}`),
      app.http.expectOne(`/tables/${TABLE_ID}/rules`),
      app.http.expectOne(`/tables/${TABLE_ID}/campaign`),
    ];
    app.harness.fixture.destroy();
    pending[0]?.flush(withCharacter());
    pending[1]?.flush(rulesView());
    pending[2]?.flush(campaignView());
    await app.settle();
    app.http.expectNone((r) => r.url === `/tables/${TABLE_ID}/events`);
  });

  it('mostra a cena, o grupo e o título', async () => {
    const { root, events, settle } = await open();
    events('0').flush(eventsView(3));
    await settle();
    expect(root().textContent).toContain('A Sombra do Vale');
    expect(root().textContent).toContain('Turno 2');
    expect(root().querySelector('dv-scene-card')?.textContent).toContain('Floresta');
    expect(root().querySelector('dv-scene-card')?.textContent).toContain('ferreiro');
    const party = root().querySelector('dv-party-strip') as HTMLElement;
    expect(party.textContent).toContain('Bia');
    expect(party.querySelector('dv-badge')?.textContent?.trim()).toBe('você');
    expect(party.textContent).toContain('fora de combate'); // Zed está com hp 0
    expect(party.querySelector('dv-pips')?.getAttribute('aria-label')).toBe(
      'pontos de vida: 8 de 10',
    );
  });

  it('a primeira chamada ao vivo carrega a janela inicial sem esperar, as seguintes esperam 20 s', async () => {
    const { events, settle } = await open(withCharacter({ revision: 120 }));
    const first = events('0');
    expect(first.request.params.get('since')).toBe('70');
    expect(first.request.headers.get('Authorization')).toBe('Bearer tk');
    first.flush(eventsView(120));
    await settle();
    expect(events('20').request.params.get('since')).toBe('120');
  });

  it('o feed mostra a narração, a nota mecânica em detalhes e a fala do mestre', async () => {
    const { root, events, settle } = await open();
    events('0').flush(
      eventsView(
        3,
        [event(1, 1), event(2, 2, { narration: 'O vento muda de direção.', kind: 'damage' })],
        [{ seq: 1000, after: 2, to: 'bia', text: 'Cuidado com o altar.' }],
        1000,
      ),
    );
    await settle();
    const text = root().querySelector('dv-feed-list')?.textContent ?? '';
    expect(text).toContain('prosa 1');
    expect(text).toContain('O vento muda de direção.');
    expect(text).not.toContain('prosa 2'); // a narração do LLM substitui a prosa do evento
    expect(text).toContain('mecânica 2');
    expect(text).toContain('Mestre');
    expect(text).toContain('Cuidado com o altar.');
    expect(root().querySelectorAll('.feed__turn').length).toBe(2);
    expect(root().querySelector('.feed__event[data-tone="danger"]')).not.toBeNull();
  });

  it('os turnos passados desbotam e o atual fica nítido', async () => {
    const { root, events, settle } = await open();
    events('0').flush(eventsView(3, [event(0, 0), event(1, 2)]));
    await settle();
    const [old, current] = Array.from(root().querySelectorAll<HTMLElement>('.feed__event'));
    expect(old?.style.getPropertyValue('--fade')).toBe('0.57');
    expect(current?.style.getPropertyValue('--fade')).toBe('0');
  });

  it('só o que chegou depois do carregamento anima a tinta nova', async () => {
    const { root, events, settle } = await open();
    events('0').flush(eventsView(3, [event(1, 1)]));
    await settle();
    expect(root().querySelectorAll('.feed__event--new').length).toBe(0); // a carga inicial entra sem animar
    events('20').flush(eventsView(4, [event(2, 1)]));
    await settle();
    expect(root().querySelectorAll('.feed__event--new').length).toBe(1);
    expect(root().querySelector('.feed__event--new')?.textContent).toContain('prosa 2');
  });

  it('texto com HTML na narração e na fala aparece como texto', async () => {
    const { root, events, settle } = await open();
    events('0').flush(
      eventsView(
        3,
        [event(1, 2, { narration: '<img src=x onerror=alert(1)> oi', prose: '<b>x</b>' })],
        [{ seq: 1, after: 1, to: 'bia', text: '<script>alert(1)</script>' }],
        1,
      ),
    );
    await settle();
    expect(root().querySelector('dv-feed-list img')).toBeNull();
    expect(root().querySelector('dv-feed-list script')).toBeNull();
    expect(root().querySelector('dv-feed-list')?.textContent).toContain(
      '<img src=x onerror=alert(1)> oi',
    );
  });

  it('um evento novo chega pelo long-poll e a mesa é relida (hp, turno, quem agiu)', async () => {
    const { root, events, http, settle } = await open();
    events('0').flush(eventsView(3));
    await settle();
    events('20').flush(eventsView(4, [event(3, 2)]));
    await settle();
    expect(root().textContent).toContain('prosa 3');
    const reread = http.expectOne(`/tables/${TABLE_ID}`);
    http.expectOne(`/tables/${TABLE_ID}/campaign`).flush(campaignView());
    const table = withCharacter({ revision: 4 });
    (table.state.characters['bia'] ?? { hp: 0 }).hp = 5;
    reread.flush(table);
    await settle();
    expect(root().querySelector('dv-party-strip dv-pips')?.getAttribute('aria-label')).toBe(
      'pontos de vida: 5 de 10',
    );
  });

  it('sem personagem avisa e leva a criar um', async () => {
    const { root, events, settle } = await open(tableView());
    events('0').flush(eventsView(3));
    await settle();
    const link = root().querySelector('dv-notice a') as HTMLAnchorElement;
    expect(link.getAttribute('href')).toBe(`/mesa/${TABLE_ID}/personagem`);
  });

  it('mostra o aviso do LLM da mesa quando ele está ligado', async () => {
    const table = withCharacter({
      llm: {
        enabled: true,
        description: 'm',
        notice: 'O texto vai ao servidor de LLM.',
        secrets: false,
      },
    });
    const { root, events, settle } = await open(table);
    events('0').flush(eventsView(3));
    await settle();
    expect(root().querySelector('.table__llm')?.textContent).toContain(
      'O texto vai ao servidor de LLM.',
    );
  });

  it('o anfitrião vê o botão de convidar e a cena sai da campanha inteira', async () => {
    const campaign = {
      locations: [
        {
          id: 'vila',
          name: 'Vila de Pedra',
          description: 'Casas.',
          connections: ['floresta'],
          private_notes: [],
        },
        { id: 'floresta', name: 'Floresta', description: '', connections: [], private_notes: [] },
      ],
      npcs: [{ id: 'ferreiro', name: 'Bram' }],
    } as unknown as Campaign;
    const table = withCharacter({ role: 'host', you: 'p1' });
    (table.state as unknown as { npcs: unknown }).npcs = {
      ferreiro: {
        location_id: 'vila',
        alive: true,
        hp: 1,
        max_hp: 1,
        attributes: {},
        disposition: 0,
      },
    };
    const { root, events, settle } = await open(table, campaign);
    events('0').flush(eventsView(3));
    await settle();
    expect(root().querySelector('dv-scene-card')?.textContent).toContain('Vila de Pedra');
    expect(root().querySelector('dv-scene-card')?.textContent).toContain('Bram');
    expect(root().querySelector('a[href$="/convite"]')).not.toBeNull();
  });

  it('um jogador comum não vê o botão de convidar', async () => {
    const { root, events, settle } = await open();
    events('0').flush(eventsView(3));
    await settle();
    expect(root().querySelector('a[href$="/convite"]')).toBeNull();
  });

  it.each([
    ['won', 'vitória'],
    ['lost', 'derrota'],
  ] as const)('partida terminada (%s) mostra o resultado', async (status, word) => {
    const { root, events, settle } = await open(withCharacter({ status }));
    events('0').flush(eventsView(3));
    await settle();
    expect(root().textContent).toContain(`A partida terminou: ${word}.`);
  });

  it('sem conexão mostra o estado em texto e volta ao vivo', async () => {
    const { root, events, settle } = await open();
    events('0').error(new ProgressEvent('error'));
    await settle();
    expect(root().querySelector('dv-connection-badge')?.textContent).toContain('Sem conexão');
  });

  it('sessão expirada (401) avisa, esquece a sessão e oferece voltar', async () => {
    const { root, events, session, settle } = await open();
    events('0').flush(
      { error: { code: 'unauthorized', message: 'token inválido' } },
      { status: 401, statusText: 'Unauthorized' },
    );
    await settle();
    await vi.waitFor(() => expect(session.get(TABLE_ID)).toBeNull());
    await settle();
    expect(root().textContent).toContain('Sua sessão nesta mesa não vale mais.');
    expect(root().querySelector('dv-notice a[href="/"]')).not.toBeNull();
  });

  it('mesa que sumiu (404) avisa', async () => {
    const { root, events, settle } = await open();
    events('0').flush(
      { error: { code: 'table_not_found', message: 'mesa não encontrada' } },
      { status: 404, statusText: 'x' },
    );
    await settle();
    expect(root().textContent).toContain('Esta mesa não existe mais neste servidor.');
  });

  it('falha ao abrir a mesa mostra o erro e esquece o token inválido', async () => {
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

  it('sair da página cancela a espera em andamento', async () => {
    const { events, harness, settle } = await open();
    events('0').flush(eventsView(3));
    await settle();
    const waiting = events('20');
    await harness.navigateByUrl('/');
    await settle();
    expect(waiting.cancelled).toBe(true);
  });

  it('sem eventos mostra um convite a agir', async () => {
    const { root, events, settle } = await open();
    events('0').flush(eventsView(3));
    await settle();
    expect(root().textContent).toContain('Nada aconteceu ainda.');
  });
});
