import { hostCampaign as campaign, hostState as state } from '../../testing/fixtures';
import { hostViewOf, isFullCampaign } from './host';

describe('visão do anfitrião', () => {
  it('só existe com a campanha inteira e o estado inteiro', () => {
    expect(hostViewOf(null, state())).toBeNull();
    expect(hostViewOf(campaign, null)).toBeNull();
    const view = {
      id: 'c',
      title: 'C',
      premise: 'p',
      location: {},
      npcs: [],
      beats: [],
      facts: [],
    };
    expect(isFullCampaign(view as never)).toBe(false);
    expect(hostViewOf(view as never, state())).toBeNull();
    const player = { ...state(), rng_seed: undefined };
    delete (player as Partial<import('@contract/api_responses').GameState>).rng_seed;
    expect(hostViewOf(campaign, player as never)).toBeNull();
  });

  it('marcos com status e o motivo de cada botão bloqueado', () => {
    const [chegada, altar] = hostViewOf(campaign, state())?.beats ?? [];
    expect(chegada).toMatchObject({
      status: 'active',
      activateBlock: 'Este marco está ativo.',
      finishBlock: '',
    });
    expect(altar?.status).toBe('pending');
    expect(altar?.activateBlock).toBe('Falta concluir: Chegada.');
    expect(altar?.finishBlock).toContain('pendente');
    expect(altar?.requires).toEqual([{ id: 'chegada', title: 'Chegada', done: false }]);
    expect(altar?.notes).toEqual(['a chave está no poco']);
    const done = hostViewOf(campaign, state({ beats: { chegada: 'done', altar: 'pending' } }));
    expect(done?.beats[1]?.activateBlock).toBe('');
  });

  it('fatos revelados e ocultos, com o nome de quem falam', () => {
    const [culto, poco] = hostViewOf(campaign, state())?.facts ?? [];
    expect(culto).toMatchObject({ about: 'Bram', revealedTurn: 3 });
    expect(poco).toMatchObject({ about: null, revealedTurn: null });
  });

  it('NPCs com hp, local e notas; locais com o atual marcado', () => {
    const view = hostViewOf(campaign, state());
    expect(view?.npcs[0]).toMatchObject({
      name: 'Bram',
      location: 'Vila',
      hp: 6,
      alive: true,
      disposition: 2,
    });
    expect(view?.npcs[1]).toMatchObject({ location: 'sem local', alive: false });
    expect(view?.locations.map((l) => [l.id, l.current])).toEqual([
      ['vila', true],
      ['floresta', false],
    ]);
    expect(view?.locations[0]?.notes).toEqual(['túnel sob a forja']);
  });

  it('alvos: os personagens e só os NPCs vivos', () => {
    expect(hostViewOf(campaign, state())?.targets).toEqual([
      { id: 'bia', name: 'Bia', kind: 'character' },
      { id: 'ferreiro', name: 'Bram', kind: 'npc' },
    ]);
  });
});
