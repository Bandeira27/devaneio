import { INVITE, TABLE_ID } from '../../../../testing/fixtures';
import { setup } from '../../../../testing/setup';

const CAMPAIGNS = [
  { id: 'sombra-do-vale', title: 'A Sombra do Vale', premise: 'Um culto desperta.' },
  { id: 'outra', title: 'Outra Campanha', premise: 'x' },
];

const NOT_FOUND = { error: { code: 'not_found', message: 'x' } };

describe('Home', () => {
  /** Abre a tela inicial e responde ao que ela pergunta: as campanhas e se o editor está ligado. */
  async function open(
    options: { editor?: boolean; seed?: (app: Awaited<ReturnType<typeof setup>>) => void } = {},
  ) {
    const app = await setup('/');
    options.seed?.(app);
    app.http.expectOne('/campaigns').flush(CAMPAIGNS);
    const probe = app.http.expectOne('/editor/campaigns');
    if (options.editor === true) {
      probe.flush([]);
    } else {
      probe.flush(NOT_FOUND, { status: 404, statusText: 'x' });
    }
    await app.settle();
    return app;
  }

  const saved = (over: object = {}) => ({
    token: 'a',
    playerId: 'p1',
    role: 'host' as const,
    title: 'A Sombra do Vale',
    savedAt: Date.now(),
    ...over,
  });

  it('lista as campanhas do servidor em cards que abrem a campanha', async () => {
    const { root } = await open();
    expect(root().querySelector('h1')?.textContent).toContain('Suas campanhas');
    const cards = Array.from(root().querySelectorAll('a.card'));
    expect(cards.map((c) => c.getAttribute('href'))).toEqual(['/c/sombra-do-vale', '/c/outra']);
    expect(cards[0]?.textContent).toContain('A Sombra do Vale');
    expect(cards[0]?.textContent).toContain('Um culto desperta.');
    expect(cards[0]?.querySelector('dv-emblem')).not.toBeNull();
  });

  it('os cards entram em sequência, no máximo três passos', async () => {
    const { root } = await open();
    const steps = Array.from(root().querySelectorAll<HTMLElement>('.cards__item')).map((el) =>
      el.style.getPropertyValue('--i'),
    );
    expect(steps).toEqual(['0', '1']);
  });

  it('o card marca quantas mesas a campanha tem neste aparelho; as antigas casam pelo título', async () => {
    const { root } = await open({
      seed: (app) => {
        app.session.save(TABLE_ID, saved({ campaignId: 'sombra-do-vale' }));
        app.session.save('1111111111111111', saved({ savedAt: 5 })); // sem o id: casa pelo título
      },
    });
    const [first, second] = Array.from(root().querySelectorAll('a.card'));
    expect(first?.textContent).toContain('2 mesas');
    expect(second?.textContent).not.toContain('mesa');
  });

  it('com mesa guardada oferece continuar a mais recente; sem mesa, a seção nem aparece', async () => {
    const none = await open();
    expect(none.root().querySelector('.home__resume')).toBeNull();
  });

  it('"Continuar de onde parou" leva à mesa guardada mais recente', async () => {
    const { root } = await open({
      seed: (app) => {
        app.session.save(TABLE_ID, saved({ title: 'Nova', savedAt: 20 }));
        app.session.save(
          '1111111111111111',
          saved({ role: 'player', title: 'Velha', savedAt: 10 }),
        );
      },
    });
    const link = root().querySelector('.home__resume a') as HTMLAnchorElement;
    expect(link.getAttribute('href')).toBe(`/mesa/${TABLE_ID}`);
    expect(root().querySelector('.home__resume')?.textContent).toContain('Nova');
    expect(root().querySelector('.home__resume')?.textContent).toContain('anfitrião');
  });

  describe('editor de campanhas', () => {
    it('com o editor ligado o último card é "Nova campanha"', async () => {
      const { root } = await open({ editor: true });
      const card = root().querySelector('a.card--new') as HTMLAnchorElement;
      expect(card.getAttribute('href')).toBe('/c/nova/roteiro');
      expect(card.textContent).toContain('Nova campanha');
    });

    it('sem o editor (404) a lista não oferece a campanha nova', async () => {
      const { root } = await open();
      expect(root().querySelector('a.card--new')).toBeNull();
    });
  });

  it('se as campanhas não carregam, mostra o erro e deixa tentar de novo', async () => {
    const app = await setup('/');
    app.http.expectOne('/campaigns').error(new ProgressEvent('error'));
    app.http.expectOne('/editor/campaigns').flush(NOT_FOUND, { status: 404, statusText: 'x' });
    await app.settle();
    expect(app.root().querySelector('[role="alert"]')?.textContent).toContain(
      'Sem conexão com o servidor',
    );
    await app.click('dv-state button');
    app.http.expectOne('/campaigns').flush(CAMPAIGNS);
    app.http.expectOne('/editor/campaigns').flush(NOT_FOUND, { status: 404, statusText: 'x' });
    await app.settle();
    expect(app.root().querySelector('a.card')).not.toBeNull();
  });

  it('um servidor sem campanhas avisa em vez de mostrar uma grade vazia', async () => {
    const app = await setup('/');
    app.http.expectOne('/campaigns').flush([]);
    app.http.expectOne('/editor/campaigns').flush(NOT_FOUND, { status: 404, statusText: 'x' });
    await app.settle();
    expect(app.root().textContent).toContain('Ainda não há campanhas');
    expect(app.root().querySelector('a.card')).toBeNull();
  });

  describe('convite', () => {
    async function paste(text: string) {
      const app = await open();
      const input = Array.from(app.root().querySelectorAll('input')).find(
        (i) => i.autocomplete === 'off',
      ) as HTMLInputElement;
      input.value = text;
      input.dispatchEvent(new Event('input'));
      await app.settle();
      (app.root().querySelector('form') as HTMLFormElement).dispatchEvent(
        new Event('submit', { cancelable: true }),
      );
      await app.settle();
      return app;
    }

    it('abre um link de convite colado', async () => {
      const { router } = await paste(`http://192.168.0.5:8765/#/entrar/${TABLE_ID}/${INVITE}`);
      await vi.waitFor(() => expect(router.url).toBe(`/entrar/${TABLE_ID}/${INVITE}`));
    });

    it('recusa texto que não é um convite', async () => {
      const { root, router } = await paste('oi, tudo bem?');
      expect(root().textContent).toContain('não parece um link de convite');
      expect(router.url).toBe('/');
    });
  });
});
