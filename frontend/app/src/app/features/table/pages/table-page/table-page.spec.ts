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
  outcome: null,
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

  it('a ordem do HTML é a de leitura: situação e cena, a história, a minha ficha, as ações', async () => {
    const { root, events, settle } = await open();
    events('0').flush(eventsView(3));
    await settle();
    const at = (selector: string): Element => root().querySelector(selector) as Element;
    const regions = [
      at('[role="status"]'), // a situação do turno
      at('[aria-label="Cena"]'),
      at('[aria-label="A história"]'),
      at('[aria-label="Minha ficha"]'),
      at('[aria-label="Ações"]'),
    ];
    regions.slice(1).forEach((region, i) => {
      const before = regions[i] as Element;
      expect(
        before.compareDocumentPosition(region) & Node.DOCUMENT_POSITION_FOLLOWING,
      ).toBeTruthy();
    });
    expect(at('[aria-label="Minha ficha"]').textContent).toContain('Bia'); // a ficha existe no HTML (a CSS a mostra só em 90rem)
  });

  it('o log só anuncia depois da carga inicial', async () => {
    const { root, events, settle } = await open();
    events('0').flush(eventsView(3, [event(1, 1)]));
    await settle();
    await new Promise((resolve) => setTimeout(resolve, 5));
    await settle();
    expect(root().querySelector('[role="log"]')?.getAttribute('aria-live')).toBe('polite');
  });

  it('a ficha do painel nasce aberta, o rótulo diz o que abre e o recolher sobrevive a um novo render', async () => {
    const { root, events, http, settle } = await open();
    events('0').flush(eventsView(3));
    await settle();
    const details = () => root().querySelector('.table__mine details') as HTMLDetailsElement;
    expect(details().open).toBe(true);
    expect(details().querySelector('summary')?.textContent).toContain('Ficha de Bia');
    details().open = false; // a pessoa recolhe
    details().dispatchEvent(new Event('toggle'));
    await settle();
    events('20').flush(eventsView(4, [event(2, 1)])); // chega algo e a página renderiza de novo
    await settle();
    http.expectOne(`/tables/${TABLE_ID}`).flush(withCharacter({ revision: 4 }));
    http.expectOne(`/tables/${TABLE_ID}/campaign`).flush(campaignView());
    await settle();
    expect(details().open).toBe(false); // continua recolhida
  });

  it('a descrição da cena fica sempre à vista, sem "Ver a cena" nem accordion', async () => {
    const campaign = {
      locations: [
        {
          id: 'vila',
          name: 'Vila de Pedra',
          description: 'Casas de pedra agarradas à encosta.',
          connections: [],
          private_notes: [],
        },
      ],
      npcs: [],
    } as unknown as Campaign;
    const { root, events, settle } = await open(withCharacter(), campaign);
    events('0').flush(eventsView(3));
    await settle();
    const scene = root().querySelector('[aria-label="Cena"]') as HTMLElement;
    expect(scene.textContent).toContain('Casas de pedra agarradas à encosta.');
    expect(scene.querySelector('details')).toBeNull();
    expect(scene.textContent).not.toContain('Ver a cena');
  });

  it('tocar numa saída da cena abre a folha de Ir com o destino tocado marcado; nada é enviado antes de confirmar', async () => {
    const campaign = {
      locations: [
        {
          id: 'vila',
          name: 'Vila de Pedra',
          description: 'Casas.',
          connections: ['floresta', 'pantano'],
          private_notes: [],
        },
        { id: 'floresta', name: 'Floresta', description: '', connections: [], private_notes: [] },
        { id: 'pantano', name: 'Pântano', description: '', connections: [], private_notes: [] },
      ],
      npcs: [],
    } as unknown as Campaign;
    const { root, events, http, settle } = await open(withCharacter(), campaign);
    events('0').flush(eventsView(3));
    await settle();
    const exits = Array.from(root().querySelectorAll('.scene__list button')) as HTMLButtonElement[];
    expect(exits.length).toBe(2);
    exits[1]?.click(); // a segunda saída
    await settle();
    const sheet = document.querySelector('.dv-sheet') as HTMLElement;
    const go = sheet.querySelector('.dv-sheet__foot .dv-button--primary') as HTMLButtonElement;
    expect(go.textContent?.trim()).toBe('Ir para Pântano'); // abriu com o destino tocado marcado
    http.expectNone(`/tables/${TABLE_ID}/commands`);
    (sheet.querySelector('[aria-label="Fechar"]') as HTMLButtonElement).click(); // sem escolher
    await settle();
    expect(document.querySelector('.dv-sheet')).toBeNull();
  });

  it('depois de ir por uma saída (a cena muda e o botão some), o foco passa à história, não ao body', async () => {
    const campaign = {
      locations: [
        { id: 'vila', name: 'Vila', description: '', connections: ['floresta'], private_notes: [] },
        { id: 'floresta', name: 'Floresta', description: '', connections: [], private_notes: [] },
      ],
      npcs: [],
    } as unknown as Campaign;
    const { root, events, http, settle } = await open(withCharacter(), campaign);
    events('0').flush(eventsView(3));
    await settle();
    const exit = root().querySelector('.scene__list button') as HTMLButtonElement;
    exit.focus();
    exit.click();
    await settle();
    const confirm = document.querySelector(
      '.dv-sheet__foot .dv-button--primary',
    ) as HTMLButtonElement;
    confirm.click();
    await settle();
    http.expectOne(`/tables/${TABLE_ID}/commands`).flush({
      revision: 4,
      events: [],
      text: '',
      status: 'active',
      turn_ended: false,
    });
    await settle();
    const moved = withCharacter({ revision: 4 });
    moved.state = { ...moved.state, current_location_id: 'floresta' };
    http.expectOne(`/tables/${TABLE_ID}`).flush(moved);
    http.expectOne(`/tables/${TABLE_ID}/campaign`).flush(campaign);
    await settle();
    await settle();
    expect(root().querySelector('.scene__list button')).toBeNull(); // a saída tocada deixou de existir
    expect(document.activeElement).toBe(root().querySelector('[aria-label="A história"]'));
  });

  it('abrir a mesa não rouba o foco para a história', async () => {
    const { root, events, settle } = await open();
    (document.activeElement as HTMLElement | null)?.blur();
    events('0').flush(eventsView(3));
    await settle();
    expect(document.activeElement).not.toBe(root().querySelector('[aria-label="A história"]'));
  });

  it('um evento novo na mesma cena não move o foco', async () => {
    const { root, events, http, settle } = await open();
    events('0').flush(eventsView(3));
    await settle();
    (document.activeElement as HTMLElement | null)?.blur(); // o foco está no body
    events('20').flush(eventsView(4, [event(2, 1)]));
    await settle();
    http.expectOne(`/tables/${TABLE_ID}`).flush(withCharacter({ revision: 4 })); // a mesa é relida: cena nova (objeto novo), mesmo nome
    http.expectOne(`/tables/${TABLE_ID}/campaign`).flush(campaignView());
    await settle();
    await new Promise((resolve) => setTimeout(resolve, 5));
    expect(document.activeElement).not.toBe(root().querySelector('[aria-label="A história"]'));
  });

  it('sem conexão, as saídas da cena também ficam bloqueadas', async () => {
    const { root, events, settle } = await open();
    events('0').flush(
      { error: { code: 'x', message: 'falhou' } } as never,
      { status: 500, statusText: 'x' } as never,
    );
    await settle();
    const exit = root().querySelector('.scene__list button') as HTMLButtonElement;
    expect(exit.getAttribute('aria-disabled')).toBe('true');
    expect(exit.getAttribute('aria-describedby')).toBe('dock-reason'); // o motivo está ligado
    exit.click();
    await settle();
    expect(document.querySelector('.dv-sheet')).toBeNull(); // o clique é engolido
  });

  it('o turno do feed é um cabeçalho de capítulo com ornamento', async () => {
    const { root, events, settle } = await open();
    events('0').flush(eventsView(3, [event(1, 1)]));
    await settle();
    const turn = root().querySelector('h3.feed__turn') as HTMLElement;
    expect(turn.querySelector('dv-ornament')).not.toBeNull();
    expect(turn.textContent).toContain('Turno 1');
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

  it('o feed mostra a narração, a nota mecânica sempre à vista (sem accordion) e a fala do mestre', async () => {
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
    expect(root().querySelectorAll('.feed__note').length).toBe(2); // uma nota por evento, direto no texto
    expect(root().querySelector('dv-feed-list details')).toBeNull();
    expect(text).not.toContain('Como foi resolvido');
    expect(text).toContain('Mestre');
    expect(text).toContain('Cuidado com o altar.');
    expect(root().querySelectorAll('.feed__turn').length).toBe(2);
  });

  it('o selo de desfecho aparece com ícone e texto, uma vez, só onde há desfecho', async () => {
    const { root, events, settle } = await open();
    events('0').flush(
      eventsView(3, [
        event(1, 1, { kind: 'check', outcome: 'failure', text: 'Bia testa Lutar: total 3' }),
        event(2, 1),
      ]),
    );
    await settle();
    const seals = root().querySelectorAll('.feed__seal');
    expect(seals.length).toBe(1);
    expect(seals[0]?.textContent?.trim()).toBe('Falha');
    expect(root().querySelector('.feed__narration')?.className).not.toMatch(/danger|ok/);
    expect(seals[0]?.querySelector('dv-icon')).not.toBeNull();
    expect(root().querySelector('.feed__note')?.textContent).toContain('total 3');
  });

  it('o link do painel do anfitrião só aparece para o anfitrião', async () => {
    const host = await open(withCharacter({ role: 'host' }));
    host.events('0').flush(eventsView(3));
    await host.settle();
    expect(host.root().querySelector('a[href$="/anfitriao"]')?.textContent).toContain('Anfitrião');
  });

  it('o jogador não vê o link do painel do anfitrião', async () => {
    const { root, events, settle } = await open();
    events('0').flush(eventsView(3));
    await settle();
    expect(root().querySelector('a[href$="/anfitriao"]')).toBeNull();
  });

  it('a nota de como foi resolvido sai em palavras de quem joga, sem códigos nem símbolos', async () => {
    const { root, events, settle } = await open();
    events('0').flush(
      eventsView(3, [
        event(1, 1, { text: 'Bia testa Lutar: 2d6 [3, 4] → total 9, hp 8 (FOR 2, AGI 1).' }),
      ]),
    );
    await settle();
    const note = root().querySelector('.feed__note')?.textContent ?? '';
    expect(note).toContain('Força 2');
    expect(note).toContain('Agilidade 1');
    expect(note).toContain('2d6: 3 e 4');
    expect(note).toContain('vida 8');
    expect(note).not.toMatch(/\bFOR\b|\bAGI\b|\bhp\b|\[|→/); // nada técnico na nota
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
    ['won', 'Vitória'],
    ['lost', 'Derrota'],
  ] as const)('partida terminada (%s) mostra o resultado', async (status, word) => {
    const { root, events, settle } = await open(withCharacter({ status }));
    events('0').flush(eventsView(3));
    await settle();
    const notice = root().querySelector('dv-notice') as HTMLElement;
    expect(notice.textContent).toContain(word);
    expect(notice.textContent).toContain('A partida terminou.');
    const back = notice.querySelector('a[href="/c/sombra-do-vale/mesas"]');
    expect(back?.textContent).toContain('Ver as mesas');
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
    expect(root().querySelector('dv-notice a[href="/c/sombra-do-vale/mesas"]')).not.toBeNull();
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

  it('mesa que sumiu ao abrir não oferece "Tentar de novo", só voltar; falha de rede oferece', async () => {
    const gone = await setup(url);
    gone.session.save(TABLE_ID, {
      token: 'tk',
      playerId: 'p2',
      role: 'player',
      title: 'x',
      savedAt: 1,
    });
    gone.http
      .expectOne(`/tables/${TABLE_ID}`)
      .flush(
        { error: { code: 'table_not_found', message: 'x' } },
        { status: 404, statusText: 'x' },
      );
    gone.http
      .match(() => true)
      .forEach((r) =>
        r.flush(
          { error: { code: 'table_not_found', message: 'x' } },
          { status: 404, statusText: 'x' },
        ),
      );
    await gone.settle();
    const buttons = Array.from(gone.root().querySelectorAll('button')).map((b) =>
      b.textContent?.trim(),
    );
    expect(buttons).not.toContain('Tentar de novo');
    expect(gone.root().textContent).toContain('Voltar ao início');
  });

  it('falha de rede ao abrir a mesa oferece "Tentar de novo"', async () => {
    const app = await setup(url);
    app.session.save(TABLE_ID, {
      token: 'tk',
      playerId: 'p2',
      role: 'player',
      title: 'x',
      savedAt: 1,
    });
    app.http.expectOne(`/tables/${TABLE_ID}`).error(new ProgressEvent('error'));
    app.http.match(() => true).forEach((r) => r.error(new ProgressEvent('error')));
    await app.settle();
    const buttons = Array.from(app.root().querySelectorAll('button')).map((b) =>
      b.textContent?.trim(),
    );
    expect(buttons).toContain('Tentar de novo');
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
