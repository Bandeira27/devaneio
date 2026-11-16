import type { Campaign, CampaignView, NpcState } from '@contract/api_responses';

/** A cena atual: local, descrição, saídas e NPCs presentes. */
export interface Scene {
  name: string;
  description: string;
  exits: { id: string; name: string }[];
  npcs: { id: string; name: string }[];
}

/**
 * A cena atual. O jogador comum recebe a `CampaignView` pronta (só o que o `olhar` mostra). O anfitrião recebe
 * a `Campaign` inteira e a cena sai dela e das posições dos NPCs no estado.
 */
export function sceneOf(
  campaign: Campaign | CampaignView,
  currentLocationId: string,
  hostNpcs: Readonly<Record<string, NpcState>> = {},
): Scene {
  if ('location' in campaign) {
    return {
      name: campaign.location.name,
      description: campaign.location.description,
      exits: campaign.location.exits,
      npcs: campaign.npcs,
    };
  }
  const names = new Map(campaign.locations.map((l) => [l.id, l.name]));
  const here = campaign.locations.find((l) => l.id === currentLocationId);
  return {
    name: here?.name ?? currentLocationId,
    description: here?.description ?? '',
    exits: (here?.connections ?? []).map((id) => ({ id, name: names.get(id) ?? id })),
    npcs: campaign.npcs
      .filter((npc) => hostNpcs[npc.id]?.location_id === currentLocationId)
      .map((npc) => ({ id: npc.id, name: npc.name })),
  };
}
