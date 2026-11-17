import { INVITE, TABLE_ID, tableCreated } from '../../../../testing/fixtures';
import { setup } from '../../../../testing/setup';

const CAMPAIGNS = [
  { id: 'sombra-do-vale', title: 'A Sombra do Vale', premise: 'Um culto desperta.' },
  { id: 'outra', title: 'Outra Campanha', premise: 'x' },
];

describe('Home', () => {
  async function open() {
    const app = await setup('/');
    app.http.expectOne('/campaigns').flush(CAMPAIGNS);
    await app.settle();
    return app;
  }

  it('lista as campanhas do servidor e escolhe a primeira', async () => {
    const { root } = await open();
    const options = Array.from(root().querySelectorAll('select option')).map((o) =>
      o.textContent?.trim(),
    );
    expect(options).toEqual(['A Sombra do Vale', 'Outra Campanha']);
    expect((root().querySelector('select') as HTMLSelectElement).value).toBe('sombra-do-vale');
  });

  it('a capa (apresentação e campanha) vem antes do painel de ações, com ou sem mesas guardadas', async () => {
    const { root } = await open();
    const cover = root().querySelector('.dv-stage__context') as HTMLElement;
    const actions = root().querySelector('.dv-stage__task') as HTMLElement;
    expect(cover.compareDocumentPosition(actions) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(actions.querySelector('form')).not.toBeNull();
    expect(root().querySelector('.home__saved')).toBeNull(); // sem mesas, a capa não tem a lista
    expect(root().querySelector('h1')?.textContent).toContain('mestre que tece a história');
  });

  it('a mesa guardada mais recente é "Continuar" (primário); as outras são "Abrir"', async () => {
    const app = await setup('/');
    app.session.save(TABLE_ID, {
      token: 'a',
      playerId: 'p1',
      role: 'host',
      title: 'Nova',
      savedAt: 20,
    });
    app.session.save('1111111111111111', {
      token: 'b',
      playerId: 'p2',
      role: 'player',
      title: 'Velha',
      savedAt: 10,
    });
    app.http.expectOne('/campaigns').flush(CAMPAIGNS);
    await app.settle();
    const links = Array.from(app.root().querySelectorAll('.saved__link')) as HTMLElement[];
    expect(links.map((l) => l.textContent?.trim())).toEqual(['Continuar', 'Abrir']);
    expect(links[0]?.classList.contains('dv-button--primary')).toBe(true);
    expect(links[1]?.classList.contains('dv-button--primary')).toBe(false);
  });

  it('mostra a premissa da campanha escolhida', async () => {
    const { root, type } = await open();
    expect(root().querySelector('.home__premise')?.textContent).toContain('Um culto desperta.');
    await type('select', 'outra');
    expect(root().querySelector('.home__premise')?.textContent).toBe('x');
  });

  it('mesa guardada mostra o papel e quando foi; "Esquecer" pode ser desfeito', async () => {
    const app = await setup('/');
    app.session.save(TABLE_ID, {
      token: 'tk',
      playerId: 'p1',
      role: 'host',
      title: 'A Sombra do Vale',
      invite: INVITE,
      savedAt: Date.now(),
    });
    app.http.expectOne('/campaigns').flush(CAMPAIGNS);
    await app.settle();
    const { root, session, click, settle } = app;
    expect(root().querySelector('.saved__item')?.textContent).toContain('anfitrião · hoje');
    await click('.saved__forget');
    expect(session.get(TABLE_ID)).toBeNull();
    expect(root().textContent).toContain('esquecida neste aparelho');
    const undo = Array.from(root().querySelectorAll('dv-notice button')).find(
      (b) => b.textContent?.trim() === 'Desfazer',
    ) as HTMLButtonElement;
    undo.click();
    await settle();
    expect(session.get(TABLE_ID)?.invite).toBe(INVITE); // o convite do anfitrião volta junto
    expect(root().textContent).not.toContain('esquecida neste aparelho');
  });

  it('o "desfazer" expira em 8 s e o foco vai para ele ao esquecer', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
    try {
      const app = await setup('/');
      app.session.save(TABLE_ID, {
        token: 'tk',
        playerId: 'p1',
        role: 'player',
        title: 'A Sombra do Vale',
        savedAt: Date.now(),
      });
      app.http.expectOne('/campaigns').flush(CAMPAIGNS);
      await app.settle();
      const focus = vi.spyOn(HTMLElement.prototype, 'focus');
      await app.click('.saved__forget');
      await app.settle();
      await Promise.resolve();
      expect(
        focus.mock.contexts.some((el) => (el as HTMLElement).classList.contains('home__undo')),
      ).toBe(true);
      focus.mockRestore();
      vi.advanceTimersByTime(8001);
      await app.settle();
      expect(app.root().textContent).not.toContain('esquecida neste aparelho');
      expect(app.session.get(TABLE_ID)).toBeNull(); // passou o prazo: o esquecimento vale
    } finally {
      vi.useRealTimers();
    }
  });

  it('exige o nome do anfitrião antes de criar a mesa', async () => {
    const { root, http, submit } = await open();
    await submit();
    expect(root().textContent).toContain('Escreva o seu nome.');
    http.expectNone('/tables');
  });

  it('cria a mesa, guarda a sessão do anfitrião e vai para o personagem', async () => {
    const { http, session, router, type, submit, settle } = await open();
    await type('select', 'outra');
    await type('input[autocomplete="nickname"]', '  Ana  ');
    await submit();
    const request = http.expectOne('/tables');
    expect(request.request.body).toEqual({ campaign_id: 'outra', host_name: 'Ana' });
    request.flush(tableCreated());
    await settle();
    expect(session.get(TABLE_ID)).toMatchObject({
      token: 'token-do-anfitriao',
      playerId: 'p1',
      role: 'host',
      invite: INVITE,
      title: 'A Sombra do Vale',
    });
    await vi.waitFor(() => expect(router.url).toBe(`/mesa/${TABLE_ID}/personagem`));
  });

  it('mostra o erro do servidor ao criar a mesa, como texto', async () => {
    const { root, http, type, submit, settle } = await open();
    await type('input[autocomplete="nickname"]', 'Ana');
    await submit();
    http
      .expectOne('/tables')
      .flush(
        { error: { code: 'sem_mapa', message: 'cheio <img src=x onerror=alert(1)>' } },
        { status: 409, statusText: 'Conflict' },
      );
    await settle();
    expect(root().querySelector('[role="alert"]')?.textContent).toContain(
      'Cheio <img src=x onerror=alert(1)>.',
    );
    expect(root().querySelector('img')).toBeNull();
  });

  it('se as campanhas não carregam, mostra o erro e deixa tentar de novo', async () => {
    const app = await setup('/');
    app.http.expectOne('/campaigns').error(new ProgressEvent('error'));
    await app.settle();
    expect(app.root().querySelector('[role="alert"]')?.textContent).toContain(
      'Sem conexão com o servidor',
    );
    await app.click('button');
    app.http.expectOne('/campaigns').flush(CAMPAIGNS);
    await app.settle();
    expect(app.root().querySelector('select')).not.toBeNull();
  });

  it('um servidor sem campanhas avisa em vez de mostrar um formulário vazio', async () => {
    const app = await setup('/');
    app.http.expectOne('/campaigns').flush([]);
    await app.settle();
    expect(app.root().textContent).toContain('Ainda não há campanhas');
    expect(app.root().querySelector('select')).toBeNull();
  });

  it('lista as mesas guardadas e esquece uma', async () => {
    const app = await setup('/');
    app.session.save(TABLE_ID, {
      token: 't',
      playerId: 'p2',
      role: 'player',
      title: 'A Sombra do Vale',
      savedAt: 1,
    });
    app.http.expectOne('/campaigns').flush(CAMPAIGNS);
    await app.settle();
    const link = app.root().querySelector('.saved__link') as HTMLAnchorElement;
    expect(link.getAttribute('href')).toBe(`/mesa/${TABLE_ID}`);
    expect(app.root().querySelector('.saved__item')?.textContent).toContain('jogador');
    await app.click('.saved__item button');
    expect(app.root().querySelector('.saved__item')).toBeNull();
    expect(app.session.get(TABLE_ID)).toBeNull();
  });

  it('abre um link de convite colado', async () => {
    const { router, type, root, settle } = await open();
    const input = Array.from(root().querySelectorAll('input')).find(
      (i) => i.autocomplete === 'off',
    ) as HTMLInputElement;
    expect(input).toBeDefined();
    input.value = `http://192.168.0.5:8765/#/entrar/${TABLE_ID}/${INVITE}`;
    input.dispatchEvent(new Event('input'));
    await settle();
    (root().querySelectorAll('form')[1] as HTMLFormElement).dispatchEvent(
      new Event('submit', { cancelable: true }),
    );
    await settle();
    await vi.waitFor(() => expect(router.url).toBe(`/entrar/${TABLE_ID}/${INVITE}`));
    expect(type).toBeDefined();
  });

  it('recusa texto que não é um convite', async () => {
    const { root, settle, router } = await open();
    const input = Array.from(root().querySelectorAll('input')).find(
      (i) => i.autocomplete === 'off',
    ) as HTMLInputElement;
    input.value = 'oi, tudo bem?';
    input.dispatchEvent(new Event('input'));
    await settle();
    (root().querySelectorAll('form')[1] as HTMLFormElement).dispatchEvent(
      new Event('submit', { cancelable: true }),
    );
    await settle();
    expect(root().textContent).toContain('não parece um link de convite');
    expect(router.url).toBe('/');
  });

  describe('editor de campanhas', () => {
    it('o link aparece quando o servidor tem o editor ligado', async () => {
      const app = await setup('/');
      app.http.expectOne('/campaigns').flush(CAMPAIGNS);
      app.http.expectOne('/editor/campaigns').flush([]);
      await app.settle();
      expect(app.root().querySelector('a[href="/editor"]')?.textContent).toContain(
        'Editor de campanhas',
      );
    });

    it('sem o editor (404) a home não oferece o link', async () => {
      const app = await setup('/');
      app.http.expectOne('/campaigns').flush(CAMPAIGNS);
      app.http
        .expectOne('/editor/campaigns')
        .flush({ error: { code: 'not_found', message: 'x' } }, { status: 404, statusText: 'x' });
      await app.settle();
      expect(app.root().querySelector('a[href="/editor"]')).toBeNull();
    });
  });
});
