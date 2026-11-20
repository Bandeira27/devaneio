import type { TableView } from '@contract/api_responses';
import { TABLE_ID, hostCampaign, hostState, rulesView, tableView } from '../../../testing/fixtures';
import { setup } from '../../../testing/setup';

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

/** O painel abre como folha por cima da mesa (a rota antiga leva à mesa e pede a barra): `root` é a folha. */
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
      .forEach(
        (r) =>
          !r.cancelled &&
          r.flush({ revision: 3, events: [], talk: [], talk_seq: 0, chat: [], chat_seq: 0 }),
      );
  live();
  await app.settle();
  const root = (): HTMLElement => document.querySelector('dv-host-sheet') as HTMLElement;
  const text = () => root()?.textContent ?? '';
  const type = async (selector: string, value: string): Promise<void> => {
    const input = root().querySelector(selector) as HTMLTextAreaElement;
    input.value = value;
    input.dispatchEvent(new Event('input'));
    await app.settle();
  };
  const submit = async (): Promise<void> => {
    (root().querySelector('form') as HTMLFormElement).dispatchEvent(
      new Event('submit', { cancelable: true }),
    );
    await app.settle();
  };
  const click = async (selector: string): Promise<void> => {
    (root().querySelector(selector) as HTMLElement).click();
    await app.settle();
  };
  return { ...app, page: app.root, root, text, live, type, submit, click };
}

/** Clica no botão primário da folha de confirmação aberta. */
async function confirm(settle: () => Promise<void>, label: string): Promise<void> {
  const button = Array.from(
    document.querySelectorAll<HTMLButtonElement>('.dv-sheet__foot button'),
  ).find((b) => b.textContent?.includes(label));
  button?.click();
  await settle();
}

describe('Barra do anfitrião (bottom sheet)', () => {
  it('abre como folha sobre a mesa, com as seções e a partida no topo', async () => {
    const { root, page, router } = await open();
    expect(router.url).toBe(`/mesa/${TABLE_ID}`); // a rota antiga leva à própria mesa
    expect(page().querySelector('h1')?.textContent).toContain('A Sombra do Vale'); // a mesa continua por baixo
    const headings = Array.from(root().querySelectorAll('h2')).map((h) => h.textContent?.trim());
    expect(headings).toEqual([
      'Painel do anfitrião',
      'Partida',
      'Ferramentas do turno', // sem mestre de IA o copiloto vai para depois das ferramentas do turno
      'Copiloto',
      'Marcos',
      'Fatos',
      'NPCs',
      'Locais',
    ]);
  });

  it('quem não é anfitrião volta para a mesa', async () => {
    const { router, settle } = await open(tableView({ role: 'player', you: 'p2' }), 'player');
    await settle();
    expect(router.url).toBe(`/mesa/${TABLE_ID}`);
    expect(document.querySelector('dv-host-sheet')).toBeNull(); // jogador não tem painel
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
    http.expectNone(`/tables/${TABLE_ID}/commands`); // concluir pede confirmação
    await confirm(settle, 'Concluir');
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
    http.expectNone(`/tables/${TABLE_ID}/commands`); // revelar não tem volta: pede confirmação
    await confirm(settle, 'Revelar');
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
    const root = document.querySelector('dv-host-sheet') as HTMLElement;
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

  it('sem mestre de IA o copiloto diz em uma linha que está indisponível', async () => {
    const { root } = await open();
    const panel = root().querySelector('dv-copilot-panel') as HTMLElement;
    expect(panel.textContent).toContain('Indisponível');
    expect(panel.textContent).toContain('mestre de IA');
    expect(panel.querySelector('textarea')).toBeNull();
    expect(panel.querySelector('dv-state')).toBeNull(); // não ocupa a barra com um bloco de aviso
  });

  it('sem mestre de IA as ferramentas do turno vêm antes do copiloto; com ele, depois', async () => {
    const { root } = await open();
    const part = root().querySelector('.drawer__part') as HTMLElement;
    expect(Array.from(part.children).map((c) => c.tagName.toLowerCase())).toEqual([
      'dv-turn-tools',
      'dv-copilot-panel',
    ]);
  });

  it('encerrar a partida fica à parte, sob um filete, e continua pedindo confirmação', async () => {
    const { root } = await open();
    const end = root().querySelector('.tools--end') as HTMLElement;
    expect(end.querySelector('button')?.textContent?.trim()).toBe('Encerrar a partida');
    expect(end.querySelector('button')?.classList.contains('dv-button--danger')).toBe(true);
    expect(
      root().querySelectorAll('dv-lifecycle-tools .tools:not(.tools--end) button'),
    ).toHaveLength(1); // só Pausar na outra linha
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

  it('fechar a folha não perde a resposta do copiloto: reabrir mostra a mesma', async () => {
    const llm = { enabled: true, description: 'x', notice: null, secrets: false };
    const { root, page, http, type, submit, settle, text } = await open(hostTable({ llm }));
    await type('dv-copilot-panel textarea', 'E agora?');
    await submit();
    http.expectOne(`/tables/${TABLE_ID}/copilot`).flush({ text: 'Revele o poço.' });
    await settle();
    expect(text()).toContain('Revele o poço.');
    root().querySelector<HTMLButtonElement>('button[aria-label="Fechar"]')?.click();
    await settle();
    expect(document.querySelector('dv-host-sheet')).toBeNull();
    // Fechada, a mesa avisa que há resposta nova (texto, não só cor) e o leitor de tela é avisado.
    const toggle = page().querySelector<HTMLButtonElement>('.table__host');
    expect(toggle?.textContent).toContain('resposta nova');
    expect(page().querySelector('[role="status"].dv-visually-hidden')?.textContent).toContain(
      'A resposta do copiloto chegou.',
    );
    toggle?.click();
    await settle();
    http.expectNone(`/tables/${TABLE_ID}`); // a mesma mesa: nada recarrega
    expect(text()).toContain('Revele o poço.');
  });

  it('no celular as partes do painel se escolhem (Agora, Trama, Mundo); uma de cada vez', async () => {
    const { root, click } = await open();
    const off = () =>
      Array.from(root().querySelectorAll('.drawer__part')).map((el) =>
        el.classList.contains('drawer__part--off'),
      );
    expect(off()).toEqual([false, true, true]); // abre em "Agora"
    const tabs = Array.from(root().querySelectorAll<HTMLButtonElement>('.drawer__tab'));
    expect(tabs.map((t) => t.textContent?.trim())).toEqual(['Agora', 'Trama', 'Mundo']);
    expect(tabs[0]?.getAttribute('aria-pressed')).toBe('true');
    await click('.drawer__tab:nth-child(2)');
    expect(off()).toEqual([true, false, true]);
    expect(root().querySelector('.drawer__tab:nth-child(2)')?.getAttribute('aria-pressed')).toBe(
      'true',
    );
  });

  it('cada botão repetido tem nome próprio (o marco ou o fato a que se refere)', async () => {
    const { root } = await open();
    const names = Array.from(
      root().querySelectorAll('dv-beats-panel button, dv-facts-panel button'),
    ).map((b) => b.getAttribute('aria-label'));
    expect(names).toContain('Ativar O altar'); // pendente: só Ativar
    expect(names).toContain('Concluir Chegada'); // ativo: Concluir e Falhar
    expect(names).toContain('Falhar Chegada');
    expect(names).not.toContain('Ativar Chegada'); // o que não serve no estado não aparece
    expect(names.some((n) => n?.startsWith('Revelar: A chave está no poco'))).toBe(true);
    expect(new Set(names).size).toBe(names.length);
  });

  it('o botão bloqueado aponta para o motivo escrito', async () => {
    const { root } = await open();
    const activate = root().querySelector<HTMLButtonElement>(
      'dv-beats-panel button[aria-label="Ativar O altar"]',
    );
    expect(activate?.getAttribute('aria-disabled')).toBe('true');
    const reason = root().querySelector('#' + activate?.getAttribute('aria-describedby'));
    expect(reason?.textContent).toContain('Falta concluir: Chegada.');
    const available = root().querySelector<HTMLButtonElement>(
      'dv-beats-panel button[aria-label="Concluir Chegada"]',
    );
    expect(available?.getAttribute('aria-disabled')).toBeNull();
  });

  it('Ferir abre a folha, escolhe o alvo e manda a linha', async () => {
    const { root, http, settle } = await open();
    const hurt = Array.from(
      root().querySelectorAll<HTMLButtonElement>('dv-turn-tools button'),
    ).find((b) => b.textContent?.trim() === 'Ferir');
    hurt?.click();
    await settle();
    const form = document.querySelector('dv-amount-sheet form') as HTMLFormElement;
    form.dispatchEvent(new Event('submit', { cancelable: true }));
    await settle();
    expect(http.expectOne(`/tables/${TABLE_ID}/commands`).request.body.line).toBe('ferir bia 1');
  });

  it('a pergunta ao copiloto em várias linhas vai como uma linha só (o servidor recusa quebra)', async () => {
    const llm = { enabled: true, description: 'x', notice: null, secrets: false };
    const { root, http, type, submit } = await open(hostTable({ llm }));
    await type('dv-copilot-panel textarea', 'Bram disse:\n\n  "a chave"\nE agora?');
    await submit();
    expect(http.expectOne(`/tables/${TABLE_ID}/copilot`).request.body).toEqual({
      text: 'Bram disse: "a chave" E agora?',
    });
    expect(root().querySelector('dv-copilot-panel')).not.toBeNull();
  });

  it('se a mesa não carrega, a rota antiga cai na mesa e nenhuma folha abre', async () => {
    const app = await setup(url);
    app.session.save(TABLE_ID, {
      token: 'tk',
      playerId: 'p1',
      role: 'host',
      title: 'x',
      savedAt: 1,
    });
    app.http
      .expectOne(`/tables/${TABLE_ID}`)
      .flush({ error: { code: 'x', message: 'x' } }, { status: 500, statusText: 'x' });
    app.http.expectOne(`/tables/${TABLE_ID}/rules`).flush(rulesView());
    app.http.expectOne(`/tables/${TABLE_ID}/campaign`).flush(hostCampaign);
    await app.settle();
    expect(app.router.url).toBe(`/mesa/${TABLE_ID}`);
    expect(document.querySelector('dv-host-sheet')).toBeNull();
  });

  it('na tela larga a barra se encaixa ao lado, leva o foco e o devolve ao fechar', async () => {
    vi.stubGlobal('matchMedia', () => ({ matches: true }));
    try {
      const app = await setup(`/mesa/${TABLE_ID}`);
      app.session.save(TABLE_ID, {
        token: 'tk',
        playerId: 'p1',
        role: 'host',
        title: 'x',
        savedAt: 1,
      });
      app.http.expectOne(`/tables/${TABLE_ID}`).flush(hostTable());
      app.http.expectOne(`/tables/${TABLE_ID}/rules`).flush(rulesView());
      app.http.expectOne(`/tables/${TABLE_ID}/campaign`).flush(hostCampaign);
      await app.settle();
      const toggle = () => app.root().querySelector<HTMLButtonElement>('.table__host');
      expect(app.root().querySelector('dv-host-aside')).toBeNull(); // fechada por padrão
      toggle()?.click();
      await app.settle();
      const aside = app.root().querySelector('dv-host-aside');
      expect(aside).not.toBeNull(); // a classe de entrada sai sozinha: o jsdom não tem animação
      expect(toggle()?.getAttribute('aria-expanded')).toBe('true');
      expect(document.querySelector('dv-host-sheet')).toBeNull(); // sem folha: a barra está encaixada
      expect(app.root().querySelector('.host-aside__title')?.getAttribute('tabindex')).toBe('-1'); // recebe o foco ao abrir
      app
        .root()
        .querySelector<HTMLButtonElement>('dv-host-aside [aria-label="Fechar o painel"]')
        ?.click();
      await app.settle();
      expect(app.root().querySelector('dv-host-aside')).toBeNull(); // sem animação no jsdom, sai na hora
      expect(document.activeElement).toBe(toggle());
    } finally {
      vi.unstubAllGlobals();
    }
  });
});
