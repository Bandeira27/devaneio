import type {
  Campaign,
  CampaignView,
  GameState,
  RulesView,
  TableCreated,
  TableJoined,
  TableView,
} from '@contract/api_responses';

export const TABLE_ID = '0123456789abcdef';
export const INVITE = 'Ab-_9xYz1234ABcd';

export function tableView(over: Partial<TableView> = {}): TableView {
  return {
    table_id: TABLE_ID,
    role: 'player',
    campaign: { id: 'sombra-do-vale', title: 'A Sombra do Vale', premise: 'Um culto desperta.' },
    players: [
      { id: 'p1', name: 'Ana', role: 'host', character_ids: [] },
      { id: 'p2', name: 'Bia', role: 'player', character_ids: [] },
    ],
    turn_policy: 'one_action_per_character',
    acted: {},
    revision: 3,
    status: 'active',
    llm: { enabled: false, description: null, notice: null, secrets: false },
    you: 'p2',
    state: {
      state_version: 1,
      campaign_id: 'sombra-do-vale',
      turn: 0,
      current_location_id: 'vila',
      characters: {},
      npcs: {},
      beats: {},
      revealed_facts: {},
    },
    ...over,
  };
}

export function rulesView(): RulesView {
  const attribute = (id: string, name: string) => ({
    id,
    name,
    description: `Descrição de ${name}`,
    min: 1,
    max: 5,
    default: 2,
  });
  return {
    id: 'default',
    name: 'Devaneio Básico',
    description: '',
    attributes: [attribute('FOR', 'Força'), attribute('AGI', 'Agilidade')],
    skills: [{ id: 'lutar', name: 'Lutar', description: '', formula: '2d6 + FOR' }],
    difficulties: [{ id: 'normal', name: 'Normal', value: 9 }],
    weapons: [{ id: 'punhos', name: 'Punhos', description: '', skill: 'lutar', damage: '1d3' }],
    modifiers: [],
    combat: { default_weapon: 'punhos', fallen_can_act: false },
  };
}

export function campaignView(npcIds: string[] = ['ferreiro']): CampaignView {
  return {
    id: 'sombra-do-vale',
    title: 'A Sombra do Vale',
    premise: 'Um culto desperta.',
    location: {
      id: 'vila',
      name: 'Vila',
      description: '',
      exits: [{ id: 'floresta', name: 'Floresta' }],
    },
    npcs: npcIds.map((id) => ({ id, name: id })),
    beats: [],
    facts: [],
  };
}

export function tableCreated(): TableCreated {
  return {
    table_id: TABLE_ID,
    host_token: 'token-do-anfitriao',
    invite_code: INVITE,
    table: tableView({ role: 'host', you: 'p1' }),
  };
}

export function tableJoined(): TableJoined {
  return { player_id: 'p2', token: 'token-da-bia', table: tableView() };
}

/** A campanha inteira de um anfitrião, com marcos, fatos e NPCs. */
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

export const hostCampaign: Campaign = {
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
    beatDef('altar', 'O altar', { requires: ['chegada'], private_notes: ['a chave está no poco'] }),
  ],
  facts: [fact('culto', 'Bram é do culto.', 'ferreiro'), fact('poco', 'A chave está no poco.')],
};

export function hostState(over: Partial<GameState> = {}): GameState {
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
