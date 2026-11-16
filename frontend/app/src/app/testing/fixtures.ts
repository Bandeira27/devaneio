import type {
  CampaignView,
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
