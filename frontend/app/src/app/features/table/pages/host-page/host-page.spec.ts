import type { TableView } from '@contract/api_responses';
import {
  TABLE_ID,
  hostCampaign,
  hostState,
  rulesView,
  tableView,
} from '../../../../testing/fixtures';
import { setup } from '../../../../testing/setup';

const url = `/mesa/${TABLE_ID}/anfitriao`;

function hostTable(over: Partial<TableView> = {}): TableView {
  return tableView({
    role: 'host',
    you: 'p1',
    llm: { enabled: false, description: null, notice: null, secrets: false },
    state: hostState(),
    ...over,
  });
}

async function open(table: TableView = hostTable(), role: 'host' | 'player' = 'host') {
  const app = await setup(url);
  app.session.save(TABLE_ID, { token: 'tk', playerId: 'p1', role, title: 'x', savedAt: 1 });
  app.http.expectOne(`/tables/${TABLE_ID}`).flush(table);
  app.http.expectOne(`/tables/${TABLE_ID}/rules`).flush(rulesView());
  app.http.expectOne(`/tables/${TABLE_ID}/campaign`).flush(hostCampaign);
  await app.settle();
  const live = () =>
    app.http
      .match((r) => r.url === `/tables/${TABLE_ID}/events`)
      .forEach((r) => !r.cancelled && r.flush({ revision: 3, events: [], talk: [], talk_seq: 0 }));
  live();
  await app.settle();
  const text = () => app.root().textContent ?? '';
  return { ...app, text, live };
}

describe('Painel do anfitrião', () => {
  it('mostra as seções, o turno e o caminho de volta à mesa', async () => {
    const { root, text } = await open();
    expect(root().querySelector('h1')?.textContent).toContain('Painel do anfitrião');
    const headings = Array.from(root().querySelectorAll('h2')).map((h) => h.textContent?.trim());
    expect(headings).toEqual([
      'Copiloto',
      'Ferramentas do turno',
      'Marcos',
      'Fatos',
      'NPCs',
      'Locais',
    ]);
    expect(text()).toContain('turno 4');
    expect(root().querySelector('a[href$="/mesa/' + TABLE_ID + '"]')?.textContent).toContain(
      'Voltar à mesa',
    );
  });

  it('quem não é anfitrião volta para a mesa', async () => {
    const { router, settle } = await open(tableView({ role: 'player', you: 'p2' }), 'player');
    await settle();
    expect(router.url).toBe(`/mesa/${TABLE_ID}`);
  });

  it('marcos mostram o status em texto e bloqueiam o botão que não vale com o motivo', async () => {
    const { root, text } = await open();
    expect(text()).toContain('ativo');
    expect(text()).toContain('pendente');
    expect(text()).toContain('Falta concluir: Chegada.');
    const buttons = Array.from(root().querySelectorAll<HTMLButtonElement>('dv-beats-panel button'));
    const blocked = buttons.filter((b) => b.getAttribute('aria-disabled') === 'true');
    expect(blocked.length).toBeGreaterThan(0);
    expect(blocked.every((b) => b.getAttribute('aria-describedby'))).toBe(true);
  });

  it('Concluir manda o comando do marco ativo', async () => {
    const { root, http, settle } = await open();
    const conclude = Array.from(
      root().querySelectorAll<HTMLButtonElement>('dv-beats-panel button'),
    ).find(
      (b) => b.textContent?.trim() === 'Concluir' && b.getAttribute('aria-disabled') !== 'true',
    );
    conclude?.click();
    await settle();
    const request = http.expectOne(`/tables/${TABLE_ID}/commands`);
    expect(request.request.body).toEqual({ line: 'marco concluir chegada', revision: 3 });
    request.flush({ revision: 4, events: [], text: 'ok', status: 'active', turn_ended: false });
  });

  it('o fato oculto tem o selo "Oculto" e o botão Revelar; o revelado diz o turno', async () => {
    const { root, text, http, settle } = await open();
    const facts = root().querySelector('dv-facts-panel') as HTMLElement;
    expect(facts.querySelectorAll('.item__text--secret').length).toBe(1);
    expect(facts.textContent).toContain('Oculto');
    expect(text()).toContain('Revelado no turno 3');
    const reveal = Array.from(facts.querySelectorAll('button')).find(
      (b) => b.textContent?.trim() === 'Revelar',
    );
    reveal?.click();
    await settle();
    expect(http.expectOne(`/tables/${TABLE_ID}/commands`).request.body.line).toBe('revelar poco');
  });

  it('notas privadas, descrições e nomes aparecem como texto, nunca como marcação', async () => {
    const campaign = {
      ...hostCampaign,
      npcs: hostCampaign.npcs.map((n, i) =>
        i === 0
          ? { ...n, name: '<img src=x onerror=alert(1)>', private_notes: ['<b>negrito</b>'] }
          : n,
      ),
    };
    const app = await setup(url);
    app.session.save(TABLE_ID, {
      token: 'tk',
      playerId: 'p1',
      role: 'host',
      title: 'x',
      savedAt: 1,
    });
    app.http.expectOne(`/tables/${TABLE_ID}`).flush(hostTable());
    app.http.expectOne(`/tables/${TABLE_ID}/rules`).flush(rulesView());
    app.http.expectOne(`/tables/${TABLE_ID}/campaign`).flush(campaign);
    await app.settle();
    const root = app.root();
    expect(root.querySelector('dv-world-panel img')).toBeNull();
    expect(root.querySelector('dv-world-panel b')).toBeNull();
    expect(root.textContent).toContain('<img src=x onerror=alert(1)>');
    expect(root.textContent).toContain('<b>negrito</b>');
  });

  it('NPC caído tem o selo e o hp em texto alternativo', async () => {
    const { root } = await open();
    const world = root().querySelector('dv-world-panel') as HTMLElement;
    expect(world.textContent).toContain('Caído');
    expect(world.querySelector('dv-pips')?.getAttribute('aria-label')).toBe(
      'pontos de vida: 6 de 8',
    );
    expect(world.textContent).toContain('O grupo está aqui');
  });

  it('sem mestre de IA o copiloto diz que não está disponível', async () => {
    const { root } = await open();
    const panel = root().querySelector('dv-copilot-panel') as HTMLElement;
    expect(panel.textContent).toContain('precisa de um mestre de IA');
    expect(panel.querySelector('textarea')).toBeNull();
  });

  it('o copiloto manda a pergunta e mostra a resposta como texto, só na página', async () => {
    const llm = { enabled: true, description: 'x', notice: null, secrets: false };
    const { root, http, settle, type, submit } = await open(hostTable({ llm }));
    const panel = root().querySelector('dv-copilot-panel') as HTMLElement;
    expect(panel.textContent).toContain('A resposta só você lê');
    await type('dv-copilot-panel textarea', 'Qual o próximo marco?');
    await submit();
    const request = http.expectOne(`/tables/${TABLE_ID}/copilot`);
    expect(request.request.body).toEqual({ text: 'Qual o próximo marco?' });
    expect(panel.textContent).toContain('O copiloto está pensando');
    request.flush({ text: 'Ative <img src=x onerror=alert(1)> o altar.\nDepois fale com Bram.' });
    await settle();
    expect(panel.querySelector('img')).toBeNull();
    expect(panel.querySelector('.copilot__answer')?.textContent).toContain(
      '<img src=x onerror=alert(1)>',
    );
    expect(panel.textContent).toContain('Sobre: Qual o próximo marco?');
    expect(panel.querySelector('textarea')?.value).toBe('');
    expect(JSON.stringify(localStorage)).not.toContain('altar');
  });

  it('pergunta vazia pede o texto e recusa do servidor vira frase com saída', async () => {
    const llm = { enabled: true, description: 'x', notice: null, secrets: false };
    const { root, http, settle, type, submit } = await open(hostTable({ llm }));
    await submit();
    expect(root().querySelector('dv-copilot-panel')?.textContent).toContain('Escreva a pergunta.');
    http.expectNone(`/tables/${TABLE_ID}/copilot`);
    await type('dv-copilot-panel textarea', 'oi');
    await submit();
    http
      .expectOne(`/tables/${TABLE_ID}/copilot`)
      .flush(
        { error: { code: 'copilot_rate_limited', message: 'x' } },
        { status: 429, statusText: 'x' },
      );
    await settle();
    expect(root().querySelector('dv-copilot-panel [role="alert"]')?.textContent).toContain(
      'precisa de um instante',
    );
  });

  it('Fim do turno pede confirmação antes de mandar o comando', async () => {
    const { root, http, settle } = await open();
    const end = Array.from(root().querySelectorAll<HTMLButtonElement>('dv-turn-tools button')).find(
      (b) => b.textContent?.trim() === 'Fim do turno',
    );
    end?.click();
    await settle();
    http.expectNone(`/tables/${TABLE_ID}/commands`);
    expect(document.body.textContent).toContain('Encerra o turno 4 para todos');
    const confirm = Array.from(
      document.querySelectorAll<HTMLButtonElement>('.dv-sheet__foot button'),
    ).find((b) => b.textContent?.includes('Encerrar o turno'));
    confirm?.click();
    await settle();
    expect(http.expectOne(`/tables/${TABLE_ID}/commands`).request.body.line).toBe('fim');
  });
});
