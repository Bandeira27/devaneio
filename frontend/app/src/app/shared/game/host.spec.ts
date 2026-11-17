import type { Campaign, GameState } from '@contract/api_responses';
import { hostViewOf, isFullCampaign } from './host';

const loc = (id: string, name: string, over: Partial<Campaign['locations'][number]> = {}) => ({
  id,
  name,
  description: '',
  connections: [],
  private_notes: [],
  ...over,
});
const npc = (id: string, name: string, over: Partial<Campaign['npcs'][number]> = {}) => ({
  id,
  name,
  description: '',
  location_id: null,
  faction_id: null,
  private_notes: [],
  attributes: {},
  disposition: 0,
  weapon_id: null,
  ...over,
});
const beatDef = (id: string, title: string, over: Partial<Campaign['beats'][number]> = {}) => ({
  id,
  title,
  description: '',
  requires: [],
  activate_when: [],
  complete_when: [],
  private_notes: [],
  ...over,
});
const fact = (id: string, text: string, about: string | null = null) => ({
  id,
  text,
  about,
  reveal_when: [],
});

const campaign: Campaign = {
  schema_version: 1,
  id: 'c',
  title: 'C',
  premise: 'p',
  rules_id: 'r',
  narration_id: 'n',
  start_location_id: 'vila',
  locations: [
    loc('vila', 'Vila', { description: 'Casas.', private_notes: ['túnel sob a forja'] }),
    loc('floresta', 'Floresta'),
  ],
  factions: [],
  npcs: [
    npc('ferreiro', 'Bram', { location_id: 'vila', private_notes: ['é do culto'] }),
    npc('monge', 'Vael'),
  ],
  beats: [
    beatDef('chegada', 'Chegada'),
    beatDef('altar', 'O altar', { requires: ['chegada'], private_notes: ['a chave está no poço'] }),
  ],
  facts: [fact('culto', 'Bram é do culto.', 'ferreiro'), fact('poço', 'A chave está no poço.')],
};

function state(over: Partial<GameState> = {}): GameState {
  return {
    state_version: 1,
    campaign_id: 'c',
    turn: 4,
    rng_seed: 7,
    rng_draws: 0,
    current_location_id: 'vila',
    characters: {
      bia: { id: 'bia', name: 'Bia', attributes: {}, hp: 5, max_hp: 10, inventory: [] },
    } as unknown as GameState['characters'],
    npcs: {
      ferreiro: {
        alive: true,
        hp: 6,
        max_hp: 8,
        attributes: {},
        disposition: 2,
        location_id: 'vila',
      },
      monge: { alive: false, hp: 0, max_hp: 6, attributes: {}, disposition: -3, location_id: null },
    },
    beats: { chegada: 'active', altar: 'pending' },
    revealed_facts: { culto: 3 },
    events: [],
    ...over,
  };
}

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
    delete (player as Partial<GameState>).rng_seed;
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
    expect(altar?.notes).toEqual(['a chave está no poço']);
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
