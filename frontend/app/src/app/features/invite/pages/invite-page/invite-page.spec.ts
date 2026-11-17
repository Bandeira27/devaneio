import { INVITE, TABLE_ID } from '../../../../testing/fixtures';
import { setup } from '../../../../testing/setup';

describe('Convite do anfitrião', () => {
  async function host() {
    const app = await setup('/');
    app.http.expectOne('/campaigns').flush([]);
    app.session.save(TABLE_ID, {
      token: 't',
      playerId: 'p1',
      role: 'host',
      title: 'A Sombra do Vale',
      invite: INVITE,
      savedAt: 1,
    });
    await app.harness.navigateByUrl(`/mesa/${TABLE_ID}/convite`);
    await app.settle();
    return app;
  }

  it('mostra o link com a mesa e o código, e avisa que localhost só serve neste aparelho', async () => {
    const { root } = await host();
    const input = root().querySelector('input[readonly]') as HTMLInputElement;
    expect(input.value).toBe(`${location.origin}/#/entrar/${TABLE_ID}/${INVITE}`);
    expect(root().textContent).toContain('só deste aparelho');
    expect(root().textContent).toContain(`Código do convite: ${INVITE}`);
  });

  it('o link com "Copiar" vem primeiro; endereço e código ficam em "Opções avançadas"', async () => {
    const { root } = await host();
    const section = root().querySelector('section') as HTMLElement;
    expect(section.firstElementChild?.tagName.toLowerCase()).toBe('dv-copy-field');
    const advanced = section.querySelector('dv-disclosure') as HTMLElement;
    expect(advanced.textContent).toContain('Opções avançadas');
    expect(advanced.querySelector('input:not([readonly])')).not.toBeNull();
  });

  it('troca o endereço e o aviso some', async () => {
    const { root, type } = await host();
    await type('input:not([readonly])', '192.168.0.5:8765');
    expect((root().querySelector('input[readonly]') as HTMLInputElement).value).toBe(
      `http://192.168.0.5:8765/#/entrar/${TABLE_ID}/${INVITE}`,
    );
    expect(root().textContent).not.toContain('só deste aparelho');
  });

  it('um endereço inválido mostra o erro e esconde o link', async () => {
    const { root, type } = await host();
    await type('input:not([readonly])', 'javascript:alert(1)');
    expect(root().querySelector('input[readonly]')).toBeNull();
    expect(root().querySelector('[role="alert"]')?.textContent).toContain('Escreva um endereço');
  });

  it('leva ao personagem e à mesa sem personagem', async () => {
    const { root } = await host();
    const links = Array.from(root().querySelectorAll('a[dvbutton]')).map((a) =>
      a.getAttribute('href'),
    );
    expect(links).toEqual([`/mesa/${TABLE_ID}/personagem`, `/mesa/${TABLE_ID}`]);
  });

  it('quem não é anfitrião vai para o personagem', async () => {
    const app = await setup('/');
    app.http.expectOne('/campaigns').flush([]);
    app.session.save(TABLE_ID, {
      token: 't',
      playerId: 'p2',
      role: 'player',
      title: 'x',
      savedAt: 1,
    });
    await app.harness.navigateByUrl(`/mesa/${TABLE_ID}/convite`);
    await app.settle();
    app.http.match(() => true).forEach((r) => r.flush({}, { status: 500, statusText: 'x' }));
    await vi.waitFor(() => expect(app.router.url).toBe(`/mesa/${TABLE_ID}/personagem`));
  });
});
