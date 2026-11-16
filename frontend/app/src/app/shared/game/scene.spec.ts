import type { Campaign, CampaignView, NpcState } from '@contract/api_responses';
import { sceneOf } from './scene';

const view: CampaignView = {
  id: 'c',
  title: 'C',
  premise: '',
  location: {
    id: 'vila',
    name: 'Vila',
    description: 'Casas de pedra.',
    exits: [{ id: 'floresta', name: 'Floresta' }],
  },
  npcs: [{ id: 'bram', name: 'Bram' }],
  beats: [],
  facts: [],
};

const full = {
  locations: [
    {
      id: 'vila',
      name: 'Vila',
      description: 'Casas de pedra.',
      connections: ['floresta'],
      private_notes: [],
    },
    {
      id: 'floresta',
      name: 'Floresta',
      description: '',
      connections: ['vila', 'sumiu'],
      private_notes: [],
    },
  ],
  npcs: [
    { id: 'bram', name: 'Bram' },
    { id: 'vael', name: 'Vael' },
  ],
} as unknown as Campaign;

const npc = (location: string | null): NpcState =>
  ({
    location_id: location,
    alive: true,
    hp: 1,
    max_hp: 1,
    attributes: {},
    disposition: 0,
  }) as NpcState;

describe('sceneOf', () => {
  it('o jogador usa a visão pronta, sem olhar o estado', () => {
    expect(sceneOf(view, 'qualquer')).toEqual({
      name: 'Vila',
      description: 'Casas de pedra.',
      exits: [{ id: 'floresta', name: 'Floresta' }],
      npcs: [{ id: 'bram', name: 'Bram' }],
    });
  });

  it('o anfitrião monta a cena da campanha inteira e das posições dos NPCs', () => {
    expect(sceneOf(full, 'vila', { bram: npc('vila'), vael: npc('ruinas') })).toEqual({
      name: 'Vila',
      description: 'Casas de pedra.',
      exits: [{ id: 'floresta', name: 'Floresta' }],
      npcs: [{ id: 'bram', name: 'Bram' }],
    });
  });

  it('uma saída para um local desconhecido mostra o id', () => {
    expect(sceneOf(full, 'floresta').exits).toEqual([
      { id: 'vila', name: 'Vila' },
      { id: 'sumiu', name: 'sumiu' },
    ]);
  });

  it('um local que a campanha não tem vira o próprio id, sem quebrar', () => {
    expect(sceneOf(full, 'x')).toEqual({ name: 'x', description: '', exits: [], npcs: [] });
  });

  it('NPC sem posição não aparece', () => {
    expect(sceneOf(full, 'vila', { bram: npc(null) }).npcs).toEqual([]);
  });
});
