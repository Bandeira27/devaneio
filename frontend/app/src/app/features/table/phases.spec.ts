import type { Character, TableView } from '@contract/api_responses';
import {
  INVITE,
  TABLE_ID,
  campaignView,
  hostCampaign,
  hostState,
  rulesView,
  tableView,
} from '../../testing/fixtures';
import { setup } from '../../testing/setup';

const BIA: Character = {
  id: 'bia',
  name: 'Bia',
  attributes: {},
  hp: 10,
  max_hp: 10,
  inventory: [],
};

/** A mesa vista pelo anfitrião (`p1`) ou por Bia (`p2`), na fase dada. */
function table(phase: TableView['phase'], who: 'host' | 'player', characters: Character[] = []) {
  const host = who === 'host';
  const view = tableView({
    role: who,
    you: host ? 'p1' : 'p2',
    phase,
    elapsed_seconds: 125,
    players: [
      {
        id: 'p1',
        name: 'Ana',
        role: 'host',
        character_ids: host ? characters.map((c) => c.id) : [],
      },
      {
        id: 'p2',
        name: 'Bia',
        role: 'player',
        character_ids: host ? [] : characters.map((c) => c.id),
      },
    ],
    llm: { enabled: false, description: null, notice: null, secrets: false },
  });
  view.state = {
    ...(host ? hostState() : view.state),
    characters: Object.fromEntries(characters.map((c) => [c.id, c])),
  } as TableView['state'];
  return view;
}

async function open(
  path: string,
  view: TableView,
  options: { invite?: boolean; role?: 'host' | 'player' } = {},
) {
  const app = await setup(path);
  const role = options.role ?? view.role;
  app.session.save(TABLE_ID, {
    token: 'tk',
    playerId: view.you,
    role,
    title: 'x',
    ...(options.invite === true ? { invite: INVITE } : {}),
    savedAt: 1,
  });
  app.http.expectOne(`/tables/${TABLE_ID}`).flush(view);
  app.http.expectOne(`/tables/${TABLE_ID}/rules`).flush(rulesView());
  app.http
    .expectOne(`/tables/${TABLE_ID}/campaign`)
    .flush(view.role === 'host' ? hostCampaign : campaignView());
  await app.settle();
  app.http
    .match((r) => r.url === `/tables/${TABLE_ID}/events`)
    .forEach((r) => !r.cancelled && r.flush({ revision: 3, events: [], talk: [], talk_seq: 0 }));
  await app.settle();
  const text = () => app.root().textContent ?? '';
  const buttons = (label: string) =>
    Array.from(app.root().querySelectorAll<HTMLButtonElement>('button')).filter((b) =>
      b.textContent?.includes(label),
    );
  return { ...app, text, buttons };
}

const mesa = `/mesa/${TABLE_ID}`;

/** Responde às duas leituras que uma mudança de fase dispara (a mesa e a campanha). */
async function answerReread(app: Awaited<ReturnType<typeof open>>, view: TableView) {
  app.http.expectOne(`/tables/${TABLE_ID}`).flush(view);
  app.http.expectOne(`/tables/${TABLE_ID}/campaign`).flush(hostCampaign);
  await app.settle();
}

describe('Sala de espera', () => {
  it('o anfitrião vê quem está aqui, o convite e não vê a mesa de jogo', async () => {
    const { root, text } = await open(mesa, table('lobby', 'host', [BIA]), { invite: true });
    expect(root().querySelector('dv-lobby')).not.toBeNull();
    expect(root().querySelector('.table__layout')).toBeNull(); // a história ainda não começou
    expect(text()).toContain('Sala de espera');
    expect(text()).toContain('Ana');
    expect(text()).toContain('Bia');
    expect(text()).toContain('sem personagem'); // Ana ainda não criou o dela
    const link = (root().querySelector('dv-copy-field input') as HTMLInputElement).value;
    expect(link).toContain(`/#/entrar/${TABLE_ID}/${INVITE}`);
    expect(root().querySelector('dv-play-clock')).toBeNull(); // sem tempo antes de começar
  });

  it('Iniciar campanha fica bloqueado sem personagem, com o motivo escrito', async () => {
    const { root, buttons } = await open(mesa, table('lobby', 'host'), { invite: true });
    const start = buttons('Iniciar campanha')[0] as HTMLButtonElement;
    expect(start.getAttribute('aria-disabled')).toBe('true');
    expect(
      root().querySelector(`#${start.getAttribute('aria-describedby')}`)?.textContent,
    ).toContain('Crie ao menos um personagem');
  });

  it('com personagem, Iniciar campanha manda a mudança de fase e abre a mesa', async () => {
    const app = await open(mesa, table('lobby', 'host', [BIA]), { invite: true });
    const start = app.buttons('Iniciar campanha')[0] as HTMLButtonElement;
    expect(start.getAttribute('aria-disabled')).toBeNull();
    start.click();
    await app.settle();
    const request = app.http.expectOne(`/tables/${TABLE_ID}/lifecycle`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ action: 'start', revision: 3 });
    const running = { ...table('running', 'host', [BIA]), revision: 5 };
    request.flush(running);
    await app.settle();
    await answerReread(app, running);
    expect(app.root().querySelector('dv-lobby')).toBeNull();
    expect(app.root().querySelector('.table__layout')).not.toBeNull();
    expect(app.root().querySelector('dv-play-clock')).not.toBeNull();
  });

  it('um erro ao iniciar aparece como texto e a sala continua', async () => {
    const app = await open(mesa, table('lobby', 'host', [BIA]), { invite: true });
    (app.buttons('Iniciar campanha')[0] as HTMLButtonElement).click();
    await app.settle();
    app.http
      .expectOne(`/tables/${TABLE_ID}/lifecycle`)
      .flush(
        { error: { code: 'no_characters', message: 'x' } },
        { status: 409, statusText: 'Conflict' },
      );
    await app.settle();
    expect(app.root().querySelector('[role="alert"]')?.textContent).toContain(
      'Crie ao menos um personagem',
    );
    expect(app.root().querySelector('dv-lobby')).not.toBeNull();
  });

  it('o convidado espera: sem botão de iniciar e com o caminho para criar o personagem', async () => {
    const { root, text, buttons } = await open(mesa, table('lobby', 'player'));
    expect(text()).toContain('Esperando o anfitrião iniciar');
    expect(buttons('Iniciar campanha')).toEqual([]);
    expect(root().querySelector('dv-copy-field')).toBeNull(); // o convite é do anfitrião
    expect(root().querySelector(`a[href="/mesa/${TABLE_ID}/personagem"]`)?.textContent).toContain(
      'Criar o meu personagem',
    );
  });

  it('a lista se atualiza sozinha: relê a mesa de tempos em tempos', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
    try {
      const app = await open(mesa, table('lobby', 'host', []), { invite: true });
      vi.advanceTimersByTime(4000);
      await app.settle();
      const reread = app.http.expectOne(`/tables/${TABLE_ID}`);
      reread.flush(table('lobby', 'host', [BIA]));
      app.http
        .match((r) => r.url === `/tables/${TABLE_ID}/campaign`)
        .forEach((r) => r.flush(hostCampaign));
      await app.settle();
      expect(app.text()).toContain('Bia');
    } finally {
      vi.useRealTimers();
    }
  });
});

describe('Pausa e fim', () => {
  it('pausada: o jogador lê, vê o aviso e não age; o anfitrião é avisado de que ainda pode', async () => {
    const player = await open(mesa, table('paused', 'player', [BIA]));
    expect(player.text()).toContain('Partida pausada pelo anfitrião');
    expect(player.text()).toContain('não agir');
    const go = Array.from(player.root().querySelectorAll<HTMLButtonElement>('.dock button')).find(
      (b) => b.textContent?.includes('Ir'),
    );
    expect(go?.getAttribute('aria-disabled')).toBe('true');
    expect(player.root().querySelector('dv-play-clock')?.textContent).toContain('Pausada');
  });

  it('pausada: o anfitrião continua podendo agir', async () => {
    const host = await open(mesa, table('paused', 'host', [{ ...BIA, id: 'ana', name: 'Ana' }]));
    expect(host.text()).toContain('Você ainda pode agir');
    const check = Array.from(host.root().querySelectorAll<HTMLButtonElement>('.dock button')).find(
      (b) => b.textContent?.includes('Testar'),
    );
    expect(check?.getAttribute('aria-disabled')).toBeNull();
  });

  it('encerrada: aviso, ninguém age (nem o anfitrião) e a história fica para ler', async () => {
    const host = await open(mesa, table('ended', 'host', [{ ...BIA, id: 'ana', name: 'Ana' }]));
    expect(host.text()).toContain('Partida encerrada pelo anfitrião');
    const buttons = Array.from(host.root().querySelectorAll<HTMLButtonElement>('.dock button'));
    for (const label of ['Ir', 'Testar', 'Atacar']) {
      const button = buttons.find((b) => b.textContent?.trim() === label);
      expect(button?.getAttribute('aria-disabled')).toBe('true');
    }
    expect(host.root().querySelector('dv-play-clock')?.textContent).toContain('Encerrada');
  });
});

describe('Controles da partida (painel do anfitrião)', () => {
  const painel = `${mesa}/anfitriao`;

  it('em andamento: Pausar e Encerrar, com o relógio parado no valor lido', async () => {
    const app = await open(painel, table('running', 'host', [BIA]));
    expect(app.buttons('Pausar').length).toBe(1);
    expect(app.buttons('Retomar')).toEqual([]);
    expect(app.buttons('Encerrar a partida').length).toBe(1);
    expect(app.root().querySelector('dv-lifecycle-tools dv-play-clock')?.textContent).toContain(
      'Rodando',
    );
  });

  it('Pausar manda a mudança de fase', async () => {
    const app = await open(painel, table('running', 'host', [BIA]));
    (app.buttons('Pausar')[0] as HTMLButtonElement).click();
    await app.settle();
    const request = app.http.expectOne(`/tables/${TABLE_ID}/lifecycle`);
    expect(request.request.body).toEqual({ action: 'pause', revision: 3 });
    const paused = table('paused', 'host', [BIA]);
    request.flush(paused);
    await app.settle();
    await answerReread(app, paused);
    expect(app.buttons('Retomar').length).toBe(1);
  });

  it('Encerrar pede confirmação e diz que não dá para reabrir; cancelar não manda nada', async () => {
    const app = await open(painel, table('running', 'host', [BIA]));
    (app.buttons('Encerrar a partida')[0] as HTMLButtonElement).click();
    await app.settle();
    const sheet = document.querySelector('.dv-sheet') as HTMLElement;
    expect(sheet.textContent).toContain('não dá para reabri-la');
    (sheet.querySelector('[aria-label="Fechar"]') as HTMLButtonElement).click();
    await app.settle();
    app.http.expectNone(`/tables/${TABLE_ID}/lifecycle`);
    (app.buttons('Encerrar a partida')[0] as HTMLButtonElement).click();
    await app.settle();
    const confirm = Array.from(
      document.querySelectorAll<HTMLButtonElement>('.dv-sheet__foot .dv-button--primary'),
    ).find((b) => b.textContent?.trim() === 'Encerrar');
    confirm?.click();
    await app.settle();
    expect(app.http.expectOne(`/tables/${TABLE_ID}/lifecycle`).request.body).toEqual({
      action: 'end',
      revision: 3,
    });
  });

  it('encerrada: sem botões de mudar a fase', async () => {
    const app = await open(painel, table('ended', 'host', [BIA]));
    for (const label of ['Pausar', 'Retomar', 'Encerrar a partida', 'Iniciar campanha']) {
      expect(app.buttons(label)).toEqual([]);
    }
    expect(app.text()).toContain('Encerrada: ninguém mais age');
  });
});
