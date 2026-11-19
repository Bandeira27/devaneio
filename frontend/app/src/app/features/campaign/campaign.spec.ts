import type { EditorTable } from '@contract/api_responses';
import { TABLE_ID, tableCreated } from '../../testing/fixtures';
import { setup } from '../../testing/setup';

const CAMPAIGNS = [
  { id: 'sombra-do-vale', title: 'A Sombra do Vale', premise: 'Um culto desperta.' },
  { id: 'outra', title: 'Outra Campanha', premise: 'x' },
];
const EDITOR_LIST = [{ id: 'sombra-do-vale', title: 'A Sombra do Vale', writable: true }];

type App = Awaited<ReturnType<typeof setup>>;

/** O servidor responde à lista de mesas da campanha: `null` é o aparelho que não o enxerga (de fora, ou sem editor). */
async function answerTables(app: App, rows: EditorTable[] | null = null): Promise<void> {
  await app.settle();
  for (const request of app.http.match((r) => r.url.endsWith('/tables'))) {
    if (rows === null) {
      request.flush(
        { error: { code: 'not_found', message: 'x' } },
        { status: 404, statusText: 'x' },
      );
    } else {
      request.flush(rows);
    }
  }
  await app.settle();
}

/** Abre uma campanha como o quadro dela faz: pergunta as campanhas e se o editor está ligado. */
async function open(url: string, options: { editor?: boolean } = {}) {
  const app = await setup(url);
  app.http.expectOne('/campaigns').flush(CAMPAIGNS);
  const probe = app.http.expectOne('/editor/campaigns');
  if (options.editor === true) {
    probe.flush(EDITOR_LIST);
  } else {
    probe.flush({ error: { code: 'not_found', message: 'x' } }, { status: 404, statusText: 'x' });
  }
  await answerTables(app);
  return app;
}

function labels(root: HTMLElement): string[] {
  return Array.from(root.querySelectorAll('.campaign__link')).map(
    (a) => a.textContent?.trim() ?? '',
  );
}

describe('Campanha: a barra lateral', () => {
  it('sem o editor tem só Visão geral e Mesas, e marca a página atual', async () => {
    const { root } = await open('/c/sombra-do-vale');
    expect(labels(root())).toEqual(['Visão geral', 'Mesas']);
    expect(root().querySelector('nav')?.getAttribute('aria-label')).toBe('Partes da campanha');
    expect(root().querySelector('.campaign__link--active')?.textContent).toContain('Visão geral');
    expect(root().querySelector('[aria-current="page"]')?.textContent).toContain('Visão geral');
    expect(root().querySelector('.campaign__title')?.textContent).toContain('A Sombra do Vale');
  });

  it('com o editor ligado ganha o grupo Roteiro com as seções', async () => {
    const { root } = await open('/c/sombra-do-vale', { editor: true });
    expect(labels(root())).toEqual([
      'Visão geral',
      'Mesas',
      'Geral',
      'Locais',
      'NPCs',
      'Facções',
      'Marcos',
      'Fatos',
      'Prévia',
    ]);
    expect(root().querySelector('.campaign__group-title')?.textContent).toContain('Roteiro');
  });

  it('navegar pela barra troca a página e a marca de atual', async () => {
    const { root, click } = await open('/c/sombra-do-vale');
    await click('a[href="/c/sombra-do-vale/mesas"]');
    expect(root().querySelector('h1')?.textContent).toContain('Mesas');
    expect(root().querySelector('[aria-current="page"]')?.textContent).toContain('Mesas');
  });

  it('o botão Menu abre e fecha os itens (para o celular) e diz o estado', async () => {
    const { root, click } = await open('/c/sombra-do-vale');
    const toggle = root().querySelector('.campaign__toggle') as HTMLElement;
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    expect(root().querySelector('.campaign__nav--open')).toBeNull();
    await click('.campaign__toggle');
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    expect(root().querySelector('.campaign__nav--open')).not.toBeNull();
    await click('a[href="/c/sombra-do-vale/mesas"]'); // escolher um item recolhe o menu
    expect(root().querySelector('.campaign__nav--open')).toBeNull();
  });

  it('uma campanha que o servidor não conhece diz isso e volta às campanhas', async () => {
    const app = await setup('/c/nao-existe');
    app.http.expectOne('/campaigns').flush(CAMPAIGNS);
    app.http.expectOne('/editor/campaigns').flush([]);
    await app.settle();
    await answerTables(app);
    app.http.expectOne('/campaigns').flush(CAMPAIGNS); // relê, caso tenha acabado de ser gravada
    app.http.expectOne('/editor/campaigns').flush([]);
    await app.settle();
    await answerTables(app);
    expect(app.root().textContent).toContain('Não encontrei esta campanha');
    expect(app.root().querySelector('a[href="/"]')).not.toBeNull();
  });

  it('a campanha nova só tem o roteiro, sem consultar o catálogo por ela', async () => {
    const app = await setup('/c/nova/roteiro');
    app.http.expectOne('/campaigns').flush(CAMPAIGNS);
    app.http.expectOne('/editor/campaigns').flush(EDITOR_LIST);
    await app.settle();
    expect(labels(app.root())).toEqual([
      'Geral',
      'Locais',
      'NPCs',
      'Facções',
      'Marcos',
      'Fatos',
      'Prévia',
    ]);
    expect(app.root().querySelector('.campaign__title')?.textContent).toContain('Nova campanha');
  });
});

describe('Campanha: visão geral', () => {
  it('mostra a premissa e oferece criar a primeira mesa', async () => {
    const { root } = await open('/c/sombra-do-vale');
    expect(root().querySelector('h1')?.textContent).toContain('A Sombra do Vale');
    expect(root().textContent).toContain('Um culto desperta.');
    expect(root().querySelector('.overview__actions a')?.textContent).toContain('Criar uma mesa');
  });

  it('com mesa guardada desta campanha oferece continuar a mais recente', async () => {
    const app = await setup('/c/sombra-do-vale');
    app.session.save(TABLE_ID, {
      token: 'a',
      playerId: 'p1',
      role: 'host',
      title: 'A Sombra do Vale',
      campaignId: 'sombra-do-vale',
      savedAt: Date.now(),
    });
    app.http.expectOne('/campaigns').flush(CAMPAIGNS);
    app.http.expectOne('/editor/campaigns').flush([]);
    await app.settle();
    await answerTables(app);
    const link = app.root().querySelector('.overview__actions a') as HTMLAnchorElement;
    expect(link.textContent).toContain('Continuar a mesa');
    expect(link.getAttribute('href')).toBe(`/mesa/${TABLE_ID}`);
  });
});

describe('Campanha: mesas', () => {
  const saved = {
    token: 'a',
    playerId: 'p1',
    role: 'host' as const,
    title: 'A Sombra do Vale',
    savedAt: Date.now(),
  };

  it('lista só as mesas desta campanha, e as antigas (sem o id) casam pelo título', async () => {
    const app = await setup('/c/sombra-do-vale/mesas');
    app.session.save(TABLE_ID, { ...saved, campaignId: 'sombra-do-vale' });
    app.session.save('1111111111111111', { ...saved, title: 'A Sombra do Vale', savedAt: 5 });
    app.session.save('2222222222222222', {
      ...saved,
      title: 'Outra Campanha',
      campaignId: 'outra',
      savedAt: 6,
    });
    app.http.expectOne('/campaigns').flush(CAMPAIGNS);
    app.http.expectOne('/editor/campaigns').flush([]);
    await app.settle();
    await answerTables(app);
    const items = Array.from(app.root().querySelectorAll('.saved__item')).map((el) =>
      el.getAttribute('data-table-id'),
    );
    expect(items).toEqual([TABLE_ID, '1111111111111111']);
  });

  it('criar mesa pede o nome, envia a campanha e vai ao passo do personagem', async () => {
    const app = await open('/c/sombra-do-vale/mesas');
    await app.submit();
    expect(app.root().textContent).toContain('Escreva o seu nome.');
    app.http.expectNone('/tables');
    await app.type('input[type="text"]', 'Ana');
    await app.submit();
    const request = app.http.expectOne('/tables');
    expect(request.request.body).toEqual({ campaign_id: 'sombra-do-vale', host_name: 'Ana' });
    request.flush(tableCreated());
    await app.settle();
    expect(app.router.url).toBe(`/mesa/${TABLE_ID}/personagem`); // o caminho segue: depois da mesa, o personagem
    expect(app.session.get(TABLE_ID)?.campaignId).toBe('sombra-do-vale');
  });

  it('criar mesa mostra o passo Mesa, fora do card, como nas outras telas do caminho', async () => {
    const app = await open('/c/sombra-do-vale/mesas');
    const steps = app.root().querySelector('dv-steps');
    expect(steps?.querySelector('[aria-current="step"]')?.textContent).toContain('Mesa');
    expect(steps?.closest('.dv-card')).toBeNull();
  });

  it('esquecer uma mesa pode ser desfeito', async () => {
    const app = await setup('/c/sombra-do-vale/mesas');
    app.session.save(TABLE_ID, { ...saved, campaignId: 'sombra-do-vale' });
    app.http.expectOne('/campaigns').flush(CAMPAIGNS);
    app.http.expectOne('/editor/campaigns').flush([]);
    await app.settle();
    await answerTables(app);
    await app.click('.saved__forget');
    expect(app.session.get(TABLE_ID)).toBeNull();
    expect(app.root().textContent).toContain('esquecida neste navegador');
    await app.click('.tables__undo');
    expect(app.session.get(TABLE_ID)).not.toBeNull();
    expect(app.root().querySelector('.saved__item')).not.toBeNull();
  });
});

describe('Endereços antigos do editor', () => {
  it('/editor/<id>/<seção> leva à mesma seção do roteiro da campanha', async () => {
    const app = await setup('/editor/sombra-do-vale/locais');
    expect(app.router.url).toBe('/c/sombra-do-vale/roteiro/locais');
  });

  it('/editor leva à lista de campanhas', async () => {
    const app = await setup('/editor');
    expect(app.router.url).toBe('/');
  });
});

const SERVER_TABLE: EditorTable = {
  table_id: TABLE_ID,
  phase: 'running',
  host_name: 'Ana',
  players: 2,
  updated_at: Date.now() / 1000,
};

/** O botão de uma folha aberta, pelo texto. */
function sheetButton(label: string): HTMLButtonElement | undefined {
  return Array.from(document.querySelectorAll<HTMLButtonElement>('.dv-sheet__foot button')).find(
    (b) => b.textContent?.includes(label),
  );
}

async function openWithServer(url: string, rows: EditorTable[]) {
  const app = await setup(url);
  app.http.expectOne('/campaigns').flush(CAMPAIGNS);
  app.http.expectOne('/editor/campaigns').flush(EDITOR_LIST);
  await answerTables(app, rows);
  return app;
}

describe('Campanha: o servidor manda na lista de mesas', () => {
  it('a visão geral conta as mesas do servidor que este navegador não conhece', async () => {
    const app = await openWithServer('/c/sombra-do-vale', [SERVER_TABLE]);
    const text = app.root().textContent ?? '';
    expect(text).toContain('tem 1 mesa, mas este navegador');
    expect(text).not.toContain('Você ainda não tem mesa');
    expect(app.root().querySelector('.overview__actions a')?.getAttribute('href')).toBe(
      '/c/sombra-do-vale/mesas',
    );
  });

  it('sem nenhuma mesa no servidor, a visão geral não fala em "aparelho"', async () => {
    const app = await openWithServer('/c/sombra-do-vale', []);
    expect(app.root().textContent).toContain('Você ainda não tem mesa nesta campanha.');
  });

  it('a lista de mesas mostra a mesa só do servidor, no vocabulário do jogo, com assumir e encerrar', async () => {
    const app = await openWithServer('/c/sombra-do-vale/mesas', [SERVER_TABLE]);
    const text = app.root().textContent ?? '';
    expect(text).toContain('Mesas desta campanha');
    expect(text).toContain('Mesa de Ana · em jogo · 2 jogadores · hoje');
    expect(text).toContain('Assumir como anfitrião');
    expect(text).toContain('Encerrar');
    expect(text).not.toContain(TABLE_ID);
  });

  it('uma mesa guardada que o servidor não tem mais some da lista', async () => {
    const app = await setup('/c/sombra-do-vale/mesas');
    app.session.save(TABLE_ID, {
      token: 'a',
      playerId: 'p1',
      role: 'host',
      title: 'A Sombra do Vale',
      campaignId: 'sombra-do-vale',
      savedAt: Date.now(),
    });
    app.http.expectOne('/campaigns').flush(CAMPAIGNS);
    app.http.expectOne('/editor/campaigns').flush(EDITOR_LIST);
    await answerTables(app, []);
    expect(app.root().querySelector('.saved__item')).toBeNull();
  });

  it('assumir como anfitrião confirma, guarda o token novo e abre a mesa', async () => {
    const app = await openWithServer('/c/sombra-do-vale/mesas', [SERVER_TABLE]);
    await app.click('.saved__assume');
    expect(document.body.textContent).toContain('deixam de valer');
    sheetButton('Assumir')?.click();
    await app.settle();
    const request = app.http.expectOne(`/editor/tables/${TABLE_ID}/host-access`);
    expect(request.request.method).toBe('POST');
    request.flush({
      table_id: TABLE_ID,
      player_id: 'p1',
      token: 'token-novo',
      invite_code: 'convite-novo',
    });
    await app.settle();
    const saved = app.session.get(TABLE_ID);
    expect([saved?.token, saved?.role, saved?.campaignId]).toEqual([
      'token-novo',
      'host',
      'sombra-do-vale',
    ]);
    expect(app.router.url).toBe(`/mesa/${TABLE_ID}`);
  });

  it('encerrar confirma, apaga no servidor e atualiza a lista; cancelar não manda nada', async () => {
    const app = await openWithServer('/c/sombra-do-vale/mesas', [SERVER_TABLE]);
    await app.click('[data-table-id] .dv-button--danger');
    sheetButton('Voltar')?.click();
    await app.settle();
    app.http.expectNone(`/editor/tables/${TABLE_ID}`);
    await app.click('[data-table-id] .dv-button--danger');
    sheetButton('Encerrar a mesa')?.click();
    await app.settle();
    const request = app.http.expectOne(`/editor/tables/${TABLE_ID}`);
    expect(request.request.method).toBe('DELETE');
    request.flush({ table_id: TABLE_ID });
    await answerTables(app, []);
    expect(app.root().querySelector('[data-table-id]')).toBeNull();
  });

  it('se o encerramento falha, o erro aparece e a mesa continua na lista', async () => {
    const app = await openWithServer('/c/sombra-do-vale/mesas', [SERVER_TABLE]);
    await app.click('[data-table-id] .dv-button--danger');
    sheetButton('Encerrar a mesa')?.click();
    await app.settle();
    app.http
      .expectOne(`/editor/tables/${TABLE_ID}`)
      .flush(
        { error: { code: 'internal', message: 'erro interno' } },
        { status: 500, statusText: 'x' },
      );
    await app.settle();
    expect(app.root().textContent).toContain('O servidor falhou');
    expect(app.root().querySelector('[data-table-id]')).not.toBeNull();
  });
});
