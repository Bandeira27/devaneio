import type { ArchivedTable, EditorTable } from '@contract/api_responses';
import { TABLE_ID, tableCreated } from '../../testing/fixtures';
import { setup } from '../../testing/setup';

const CAMPAIGNS = [
  { id: 'sombra-do-vale', title: 'A Sombra do Vale', premise: 'Um culto desperta.' },
  { id: 'outra', title: 'Outra Campanha', premise: 'x' },
];
const EDITOR_LIST = [{ id: 'sombra-do-vale', title: 'A Sombra do Vale', writable: true }];

type App = Awaited<ReturnType<typeof setup>>;

/** O servidor responde à lista de mesas da campanha: `null` é o aparelho que não o enxerga (de fora, ou sem editor). */
async function answerTables(
  app: App,
  rows: EditorTable[] | null = null,
  archived: ArchivedTable[] = [],
): Promise<void> {
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
  for (const request of app.http.match((r) => r.url.endsWith('/archived-tables'))) {
    if (rows === null) {
      request.flush(
        { error: { code: 'not_found', message: 'x' } },
        { status: 404, statusText: 'x' },
      );
    } else {
      request.flush(archived);
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
    expect(root().querySelector('.overview__actions a')?.getAttribute('href')).toBe(
      '/c/sombra-do-vale/nova-mesa',
    ); // sem mesa, vai direto à tela do passo
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

  it('a lista só aponta para a tela de criar: um botão, sem formulário nem passos', async () => {
    const app = await open('/c/sombra-do-vale/mesas');
    const link = app.root().querySelector('a[href="/c/sombra-do-vale/nova-mesa"]');
    expect(link?.textContent).toContain('Criar uma mesa');
    expect(app.root().querySelector('form')).toBeNull();
    expect(app.root().querySelector('dv-steps')).toBeNull();
  });

  it('sem mesa nenhuma, a lista explica o que é uma mesa antes do botão', async () => {
    const app = await open('/c/sombra-do-vale/mesas');
    expect(app.root().querySelector('#sem-mesas')?.textContent).toContain('ainda não tem mesa');
  });

  it('com mesa guardada, a explicação do estado vazio some', async () => {
    const app = await setup('/c/sombra-do-vale/mesas');
    app.session.save(TABLE_ID, { ...saved, campaignId: 'sombra-do-vale' });
    app.http.expectOne('/campaigns').flush(CAMPAIGNS);
    app.http.expectOne('/editor/campaigns').flush([]);
    await app.settle();
    await answerTables(app);
    expect(app.root().querySelector('#sem-mesas')).toBeNull();
  });

  it('criar mesa pede o nome, envia a campanha e vai ao passo do personagem', async () => {
    const app = await setup('/c/sombra-do-vale/nova-mesa'); // fora do quadro da campanha: nada a perguntar além de criar
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

  it('criar mesa é o passo Mesa no palco, à frente do contexto, com a saída para a lista abaixo do formulário', async () => {
    const app = await setup('/c/sombra-do-vale/nova-mesa'); // fora do quadro da campanha: nada a perguntar além de criar
    const context = app.root().querySelector('.dv-stage__context');
    expect(context?.firstElementChild?.tagName.toLowerCase()).toBe('dv-steps');
    expect(context?.querySelector('[aria-current="step"]')?.textContent).toContain('Mesa');
    // a saída fica junto da ação que ela cancela (abaixo do formulário), não solta na coluna de contexto
    expect(context?.querySelector('a[href="/c/sombra-do-vale/mesas"]')).toBeNull();
    const task = app.root().querySelector('.dv-stage__task');
    expect(task?.lastElementChild?.getAttribute('href')).toBe('/c/sombra-do-vale/mesas');
    expect(task?.lastElementChild?.textContent).toContain('Voltar às mesas');
    expect(app.root().querySelector('nav[aria-label="Partes da campanha"]')).toBeNull(); // sem a barra lateral: o foco é o caminho
    expect(app.root().querySelector('.campaign__link--active')).toBeNull(); // e nada de "Mesas" marcado
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

  it('a lista de mesas mostra a mesa só do servidor, no vocabulário do jogo, com assumir e arquivar', async () => {
    const app = await openWithServer('/c/sombra-do-vale/mesas', [SERVER_TABLE]);
    const text = app.root().textContent ?? '';
    expect(text).toContain('Mesas desta campanha');
    expect(text).toContain('Mesa de Ana');
    expect(text).toContain('em jogo · 2 jogadores · hoje');
    expect(text).toContain('Assumir como anfitrião');
    expect(text).toContain('Arquivar');
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

  it('arquivar confirma, arquiva no servidor e atualiza a lista; cancelar não manda nada', async () => {
    const app = await openWithServer('/c/sombra-do-vale/mesas', [SERVER_TABLE]);
    await app.click('[data-table-id] .saved__archive');
    sheetButton('Voltar')?.click();
    await app.settle();
    app.http.expectNone(`/editor/tables/${TABLE_ID}`);
    await app.click('[data-table-id] .saved__archive');
    sheetButton('Arquivar a mesa')?.click();
    await app.settle();
    const request = app.http.expectOne(`/editor/tables/${TABLE_ID}`);
    expect(request.request.method).toBe('DELETE');
    request.flush({ table_id: TABLE_ID });
    await answerTables(app, []);
    expect(app.root().querySelector('[data-table-id]')).toBeNull();
  });

  it('se o arquivamento falha, o erro aparece e a mesa continua na lista', async () => {
    const app = await openWithServer('/c/sombra-do-vale/mesas', [SERVER_TABLE]);
    await app.click('[data-table-id] .saved__archive');
    sheetButton('Arquivar a mesa')?.click();
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

describe('Campanha: mesas arquivadas', () => {
  const ARCHIVED: ArchivedTable = {
    table_id: 'aaaaaaaaaaaaaaaa',
    phase: 'running',
    host_name: 'Ana',
    players: 2,
    updated_at: 1_700_000_000,
    archived_at: 1_700_000_500,
  };
  const OPEN = { error: { code: 'not_found', message: 'x' } };

  /** Abre as mesas da campanha com o editor ligado e uma mesa arquivada no servidor. */
  async function openArchived() {
    const app = await setup('/c/sombra-do-vale/mesas');
    app.http.expectOne('/campaigns').flush(CAMPAIGNS);
    app.http.expectOne('/editor/campaigns').flush(EDITOR_LIST);
    await answerTables(app, [], [ARCHIVED]);
    return app;
  }

  function button(app: App, label: string): HTMLButtonElement | undefined {
    return Array.from(app.root().querySelectorAll('button')).find((b) =>
      b.textContent?.includes(label),
    );
  }

  it('lista as arquivadas à parte, com o vocabulário do jogo e sem ids', async () => {
    const app = await openArchived();
    const text = app.root().textContent ?? '';
    expect(text).toContain('Mesas arquivadas');
    expect(text).toContain('Mesa de Ana');
    expect(text).toContain('em jogo · 2 jogadores · jogada pela última vez');
    expect(text).not.toContain('aaaaaaaaaaaaaaaa');
    expect(button(app, 'Restaurar')).toBeDefined();
    expect(button(app, 'Ver histórico')).toBeDefined();
    expect(button(app, 'Apagar de vez')).toBeDefined();
  });

  it('sem arquivadas, a seção nem aparece', async () => {
    const app = await setup('/c/sombra-do-vale/mesas');
    app.http.expectOne('/campaigns').flush(CAMPAIGNS);
    app.http.expectOne('/editor/campaigns').flush(EDITOR_LIST);
    await answerTables(app, []);
    expect(app.root().textContent).not.toContain('Mesas arquivadas');
  });

  it('restaurar manda ao servidor e atualiza as listas, sem pedir confirmação', async () => {
    const app = await openArchived();
    button(app, 'Restaurar')?.click();
    await app.settle();
    const restore = app.http.expectOne('/editor/archived-tables/aaaaaaaaaaaaaaaa/restore');
    expect(restore.request.method).toBe('POST');
    restore.flush({
      table_id: ARCHIVED.table_id,
      phase: 'running',
      host_name: 'Ana',
      players: 2,
      updated_at: 1_700_000_500,
    });
    await answerTables(app, [], []);
    expect(app.root().textContent).not.toContain('Mesas arquivadas');
  });

  it('restaurar que o servidor recusa mostra o motivo e mantém a mesa arquivada', async () => {
    const app = await openArchived();
    button(app, 'Restaurar')?.click();
    await app.settle();
    app.http.expectOne('/editor/archived-tables/aaaaaaaaaaaaaaaa/restore').flush(
      {
        error: {
          code: 'table_unreadable',
          message: 'a partida não combina mais com a campanha: ela segue arquivada',
        },
      },
      { status: 409, statusText: 'x' },
    );
    await app.settle();
    expect(app.root().textContent).toContain('não combina mais com a campanha');
    expect(app.root().textContent).toContain('Mesas arquivadas');
  });

  it('apagar de vez confirma antes; cancelar não manda nada', async () => {
    const app = await openArchived();
    button(app, 'Apagar de vez')?.click();
    await app.settle();
    expect(document.body.textContent).toContain('Isto não tem volta');
    sheetButton('Voltar')?.click();
    await app.settle();
    app.http.expectNone('/editor/archived-tables/aaaaaaaaaaaaaaaa');
  });

  it('apagar de vez confirmado apaga no servidor e atualiza a lista', async () => {
    const app = await openArchived();
    button(app, 'Apagar de vez')?.click();
    await app.settle();
    sheetButton('Apagar de vez')?.click();
    await app.settle();
    const purge = app.http.expectOne('/editor/archived-tables/aaaaaaaaaaaaaaaa');
    expect(purge.request.method).toBe('DELETE');
    purge.flush({ table_id: ARCHIVED.table_id });
    await answerTables(app, [], []);
    expect(app.root().textContent).not.toContain('Mesas arquivadas');
  });

  it('ver histórico abre o log da mesa, em ordem, e some ao fechar', async () => {
    const app = await openArchived();
    button(app, 'Ver histórico')?.click();
    await app.settle();
    app.http.expectOne('/editor/archived-tables/aaaaaaaaaaaaaaaa/log').flush({
      table_id: ARCHIVED.table_id,
      turn: 2,
      events: [
        { index: 0, turn: 0, kind: 'start', text: 'A partida começou.' },
        { index: 1, turn: 1, kind: 'check', text: 'Ana testa lutar: sucesso.' },
        { index: 2, turn: 1, kind: 'note', text: '' },
      ],
    });
    await app.settle();
    const sheet = document.body.textContent ?? '';
    expect(sheet).toContain('Histórico: mesa de Ana');
    expect(sheet.indexOf('A partida começou.')).toBeLessThan(sheet.indexOf('Ana testa lutar'));
    expect(document.body.querySelectorAll('.history__item')).toHaveLength(2); // o evento sem texto não aparece
    sheetButton('Fechar')?.click();
    await app.settle();
    expect(document.body.querySelector('.history')).toBeNull();
  });

  it('falha ao ler o histórico mostra o erro e oferece tentar de novo', async () => {
    const app = await openArchived();
    button(app, 'Ver histórico')?.click();
    await app.settle();
    app.http
      .expectOne('/editor/archived-tables/aaaaaaaaaaaaaaaa/log')
      .flush(OPEN, { status: 404, statusText: 'x' });
    await app.settle();
    expect(document.body.textContent).toContain('Tentar de novo');
  });

  it('tentar de novo mantém o botão (e o foco) e mostra o log quando a segunda leitura dá certo', async () => {
    const app = await openArchived();
    button(app, 'Ver histórico')?.click();
    await app.settle();
    app.http
      .expectOne('/editor/archived-tables/aaaaaaaaaaaaaaaa/log')
      .flush(OPEN, { status: 404, statusText: 'x' });
    await app.settle();
    const retry = Array.from(document.body.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Tentar de novo'),
    ) as HTMLButtonElement;
    retry.focus();
    retry.click();
    await app.settle();
    expect(document.body.contains(retry)).toBe(true); // o botão não saiu da tela durante a nova tentativa
    expect(retry.getAttribute('aria-busy')).toBe('true');
    app.http.expectOne('/editor/archived-tables/aaaaaaaaaaaaaaaa/log').flush({
      table_id: ARCHIVED.table_id,
      turn: 0,
      events: [{ index: 0, turn: 0, kind: 'start', text: 'A partida começou.' }],
    });
    await app.settle();
    expect(document.body.textContent).toContain('Início');
    expect(document.body.textContent).toContain('A partida começou.');
  });

  it('o histórico vazio usa o estado de vazio da tela', async () => {
    const app = await openArchived();
    button(app, 'Ver histórico')?.click();
    await app.settle();
    app.http
      .expectOne('/editor/archived-tables/aaaaaaaaaaaaaaaa/log')
      .flush({ table_id: ARCHIVED.table_id, turn: 0, events: [] });
    await app.settle();
    expect(document.body.textContent).toContain('Esta mesa não tem nada registrado.');
  });

  it('restaurar avisa o que aconteceu e a mesa volta para a lista de cima, com o foco nela', async () => {
    const app = await openArchived();
    button(app, 'Restaurar')?.click();
    await app.settle();
    app.http.expectOne('/editor/archived-tables/aaaaaaaaaaaaaaaa/restore').flush({
      table_id: ARCHIVED.table_id,
      phase: 'running',
      host_name: 'Ana',
      players: 2,
      updated_at: 1_700_000_500,
    });
    await answerTables(
      app,
      [
        {
          table_id: ARCHIVED.table_id,
          phase: 'running',
          host_name: 'Ana',
          players: 2,
          updated_at: 1_700_000_500,
        },
      ],
      [],
    );
    const text = app.root().textContent ?? '';
    expect(text).toContain('Mesa restaurada.');
    expect(text).toContain('Assumir como anfitrião'); // reaparece na lista de cima (o navegador não tem o acesso)
    expect(text).not.toContain('Mesas arquivadas');
    expect(app.root().querySelector('[role="status"]')?.textContent).toContain('Mesa restaurada.');
    expect(document.activeElement?.classList.contains('saved__assume')).toBe(true);
  });

  it('um erro do servidor aparece uma só vez, mesmo com mesas ativas e arquivadas na tela', async () => {
    const app = await setup('/c/sombra-do-vale/mesas');
    app.http.expectOne('/campaigns').flush(CAMPAIGNS);
    app.http.expectOne('/editor/campaigns').flush(EDITOR_LIST);
    await answerTables(
      app,
      [
        {
          table_id: 'bbbbbbbbbbbbbbbb',
          phase: 'lobby',
          host_name: 'Bia',
          players: 1,
          updated_at: 1,
        },
      ],
      [ARCHIVED],
    );
    button(app, 'Restaurar')?.click();
    await app.settle();
    app.http
      .expectOne('/editor/archived-tables/aaaaaaaaaaaaaaaa/restore')
      .flush({ error: { code: 'table_limit', message: 'x' } }, { status: 409, statusText: 'x' });
    await app.settle();
    expect(app.root().querySelectorAll('[role="alert"]')).toHaveLength(1);
    expect(app.root().textContent).toContain('Arquive ou apague outra mesa');
  });

  it('arquivar e apagar de vez também avisam; as linhas arquivadas dizem quando foram jogadas', async () => {
    const app = await openArchived();
    expect(app.root().textContent).toContain('jogada pela última vez');
    button(app, 'Apagar de vez')?.click();
    await app.settle();
    expect(document.body.textContent).toContain('Mesa de Ana');
    sheetButton('Apagar de vez')?.click();
    await app.settle();
    app.http
      .expectOne('/editor/archived-tables/aaaaaaaaaaaaaaaa')
      .flush({ table_id: ARCHIVED.table_id });
    await answerTables(app, [], []);
    expect(app.root().textContent).toContain('Mesa apagada de vez.');
  });
});
