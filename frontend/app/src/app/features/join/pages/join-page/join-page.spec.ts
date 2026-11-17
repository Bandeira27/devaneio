import { INVITE, TABLE_ID, tableJoined } from '../../../../testing/fixtures';
import { setup } from '../../../../testing/setup';

describe('Entrar na mesa', () => {
  const url = `/entrar/${TABLE_ID}/${INVITE}`;

  it('com o convite do link só pede o nome', async () => {
    const { root } = await setup(url);
    expect(root().querySelectorAll('input')).toHaveLength(1);
    expect(root().textContent).toContain('Convite recebido pelo link.');
  });

  it('sem o convite pede o código', async () => {
    const { root } = await setup(`/entrar/${TABLE_ID}`);
    expect(root().querySelectorAll('input')).toHaveLength(2);
  });

  it('exige o nome', async () => {
    const { root, http, submit } = await setup(url);
    await submit();
    expect(root().textContent).toContain('Escreva o seu nome.');
    http.expectNone(`/tables/${TABLE_ID}/players`);
  });

  it('sem o convite exige o código', async () => {
    const { root, http, type, submit } = await setup(`/entrar/${TABLE_ID}`);
    await type('input[autocomplete="nickname"]', 'Bia');
    await submit();
    expect(root().textContent).toContain('Cole o código do convite.');
    http.expectNone(`/tables/${TABLE_ID}/players`);
  });

  it('entra com o convite e o nome, guarda a sessão e vai criar o personagem', async () => {
    const { http, session, router, type, submit, settle } = await setup(url);
    await type('input', '  Bia  ');
    await submit();
    const request = http.expectOne(`/tables/${TABLE_ID}/players`);
    expect(request.request.body).toEqual({ invite_code: INVITE, name: 'Bia' });
    expect(request.request.headers.has('Authorization')).toBe(false);
    request.flush(tableJoined());
    await settle();
    expect(session.get(TABLE_ID)).toMatchObject({
      token: 'token-da-bia',
      playerId: 'p2',
      role: 'player',
      title: 'A Sombra do Vale',
    });
    expect(session.get(TABLE_ID)?.invite).toBeUndefined(); // o convite é do anfitrião
    await vi.waitFor(() => expect(router.url).toBe(`/mesa/${TABLE_ID}/personagem`));
    http.match(() => true); // a página seguinte pede a mesa
  });

  it('convite recusado mostra a mensagem do servidor e continua na página', async () => {
    const { root, http, router, type, submit, settle } = await setup(url);
    await type('input', 'Bia');
    await submit();
    http
      .expectOne(`/tables/${TABLE_ID}/players`)
      .flush(
        { error: { code: 'invalid_invite', message: 'convite inválido' } },
        { status: 401, statusText: 'Unauthorized' },
      );
    await settle();
    expect(root().querySelector('[role="alert"]')?.textContent).toContain('Esse convite não vale');
    expect(router.url).toBe(url);
  });

  it.each([
    ['já existe um jogador chamado Bia', 'Já existe um jogador chamado Bia.'],
    ['a mesa já tem 8 jogadores', 'A mesa já tem 8 jogadores.'],
  ])('mostra o que o servidor disse: %s', async (message, shown) => {
    const { root, http, type, submit, settle } = await setup(url);
    await type('input', 'Bia');
    await submit();
    http
      .expectOne(`/tables/${TABLE_ID}/players`)
      .flush({ error: { code: 'x', message } }, { status: 409, statusText: 'Conflict' });
    await settle();
    expect(root().querySelector('[role="alert"]')?.textContent).toContain(shown);
  });

  it('mostra os passos (convite é o primeiro) e o contexto ao lado do formulário', async () => {
    const { root } = await setup(url);
    expect(root().querySelector('dv-steps li[aria-current="step"]')?.textContent).toContain(
      'Convite',
    );
    expect(root().querySelector('.dv-stage__context h1')?.textContent).toContain('Entrar na mesa');
    expect(root().querySelector('form.dv-stage__task')).not.toBeNull();
  });

  it('quem já entrou por este navegador vai direto para a mesa', async () => {
    const app = await setup('/');
    app.http.expectOne('/campaigns').flush([]);
    app.session.save(TABLE_ID, {
      token: 't',
      playerId: 'p2',
      role: 'player',
      title: 'x',
      savedAt: 1,
    });
    await app.harness.navigateByUrl(url);
    await app.settle();
    await vi.waitFor(() => expect(app.router.url).toBe(`/mesa/${TABLE_ID}`));
  });

  it('um nome com HTML aparece como texto no erro, sem virar elemento', async () => {
    const { root, http, type, submit, settle } = await setup(url);
    await type('input', '<img src=x onerror=alert(1)>');
    await submit();
    http
      .expectOne(`/tables/${TABLE_ID}/players`)
      .flush(
        { error: { code: 'x', message: 'nome <b>ruim</b>' } },
        { status: 422, statusText: 'x' },
      );
    await settle();
    expect(root().querySelector('b')).toBeNull();
    expect(root().querySelector('img')).toBeNull();
    expect(root().textContent).toContain('Nome <b>ruim</b>.');
  });
});
