import type { Campaign, Faction, Location, Npc } from '@contract/api_responses';
import { slugify, uniqueId } from './names';

/**
 * As edições de uma campanha no editor, como funções puras: cada uma devolve uma campanha nova e nunca muda a que
 * recebeu. O servidor é quem valida; aqui só se mantém a campanha coerente com o que o autor faz (renomear um id
 * atualiza as referências, remover um item tira o que apontava para ele).
 */

/** Os tipos de item que têm id e são citados por outros. */
export type ItemKind = 'location' | 'npc' | 'faction' | 'beat';

/** Uma campanha em branco: um local de partida e nada mais. */
export function emptyCampaign(id: string, title: string): Campaign {
  return {
    schema_version: 1,
    id,
    title,
    premise: '',
    rules_id: 'default',
    narration_id: 'pt-br',
    start_location_id: 'inicio',
    locations: [location('inicio', 'Início')],
    factions: [],
    npcs: [],
    beats: [],
    facts: [],
  };
}

/** Um local novo, sem ligações. */
export function location(id: string, name: string): Location {
  return { id, name, description: '', connections: [], private_notes: [] };
}

/** Uma facção nova. */
export function faction(id: string, name: string): Faction {
  return { id, name, description: '', goals: [], private_notes: [] };
}

/** Um NPC novo, sem local nem facção. */
export function npc(id: string, name: string): Npc {
  return {
    id,
    name,
    description: '',
    location_id: null,
    faction_id: null,
    private_notes: [],
    attributes: {},
    disposition: 0,
    weapon_id: null,
  };
}

/** Todos os ids da campanha (de qualquer tipo): um id novo não pode repetir nenhum deles dentro do seu tipo. */
export function idsOf(campaign: Campaign, kind: ItemKind): string[] {
  const lists = {
    location: campaign.locations,
    npc: campaign.npcs,
    faction: campaign.factions,
    beat: campaign.beats,
  };
  return lists[kind].map((item) => item.id);
}

/** Um id livre para um item do tipo, a partir do nome ("Vila Velha" vira `vila-velha`, `vila-velha-2`...). */
export function freeId(campaign: Campaign, kind: ItemKind, name: string, ignore?: string): string {
  const taken = idsOf(campaign, kind).filter((id) => id !== ignore);
  return uniqueId(slugify(name, kind), taken);
}

/** Acrescenta um local com um nome padrão. */
export function addLocation(campaign: Campaign, name = 'Novo local'): Campaign {
  const id = freeId(campaign, 'location', name);
  return { ...campaign, locations: [...campaign.locations, location(id, name)] };
}

/** Acrescenta um NPC. */
export function addNpc(campaign: Campaign, name = 'Novo NPC'): Campaign {
  const id = freeId(campaign, 'npc', name);
  return { ...campaign, npcs: [...campaign.npcs, npc(id, name)] };
}

/** Acrescenta uma facção. */
export function addFaction(campaign: Campaign, name = 'Nova facção'): Campaign {
  const id = freeId(campaign, 'faction', name);
  return { ...campaign, factions: [...campaign.factions, faction(id, name)] };
}

/** Troca o item da posição `index` de uma lista. */
export function replaceAt<T>(list: readonly T[], index: number, item: T): T[] {
  return list.map((current, i) => (i === index ? item : current));
}

/** Move o item uma posição para cima (`-1`) ou para baixo (`1`); nas pontas não faz nada. */
export function moveAt<T>(list: readonly T[], index: number, delta: -1 | 1): T[] {
  const target = index + delta;
  if (target < 0 || target >= list.length) {
    return [...list];
  }
  const copy = [...list];
  const [moved] = copy.splice(index, 1);
  copy.splice(target, 0, moved as T);
  return copy;
}

/**
 * Renomeia o id de um item e atualiza tudo que o citava: ligações dos locais, local de partida, local e facção dos NPCs,
 * `about` dos fatos, requisitos dos marcos e as condições (`at_location`, `npc_down`, `beat_done`).
 */
export function renameId(campaign: Campaign, kind: ItemKind, from: string, to: string): Campaign {
  if (from === to) {
    return campaign;
  }
  const swap = (id: string): string => (id === from ? to : id);
  const swapNullable = (id: string | null): string | null => (id === null ? null : swap(id));
  const conditions = <T extends { kind: string }>(list: T[]): T[] =>
    list.map((c) => {
      const cond = c as unknown as Record<string, unknown>;
      if (kind === 'location' && c.kind === 'at_location' && cond['location_id'] === from) {
        return { ...c, location_id: to };
      }
      if (kind === 'npc' && c.kind === 'npc_down' && cond['npc_id'] === from) {
        return { ...c, npc_id: to };
      }
      if (kind === 'beat' && c.kind === 'beat_done' && cond['beat_id'] === from) {
        return { ...c, beat_id: to };
      }
      return c;
    });
  const own = <T extends { id: string }>(list: T[], wanted: ItemKind): T[] =>
    kind === wanted ? list.map((item) => (item.id === from ? { ...item, id: to } : item)) : list;
  return {
    ...campaign,
    start_location_id:
      kind === 'location' ? swap(campaign.start_location_id) : campaign.start_location_id,
    locations: own(campaign.locations, 'location').map((l) =>
      kind === 'location' ? { ...l, connections: l.connections.map(swap) } : l,
    ),
    factions: own(campaign.factions, 'faction'),
    npcs: own(campaign.npcs, 'npc').map((n) => ({
      ...n,
      location_id: kind === 'location' ? swapNullable(n.location_id) : n.location_id,
      faction_id: kind === 'faction' ? swapNullable(n.faction_id) : n.faction_id,
    })),
    beats: own(campaign.beats, 'beat').map((b) => ({
      ...b,
      requires: kind === 'beat' ? b.requires.map(swap) : b.requires,
      activate_when: conditions(b.activate_when),
      complete_when: conditions(b.complete_when),
    })),
    facts: campaign.facts.map((f) => ({
      ...f,
      about: f.about === null ? null : swap(f.about), // `about` pode apontar para qualquer tipo; ids iguais em tipos diferentes são ambíguos
      reveal_when: conditions(f.reveal_when),
    })),
  };
}

/**
 * Remove um item e tira o que apontava para ele: ligações para o local, local ou facção dos NPCs (ficam sem), o
 * `about` dos fatos e os requisitos dos marcos. Condições que citam o item ficam como estão: o validador as aponta
 * e o autor decide o que fazer.
 */
export function removeItem(campaign: Campaign, kind: ItemKind, id: string): Campaign {
  const keep = <T extends { id: string }>(list: T[], wanted: ItemKind): T[] =>
    kind === wanted ? list.filter((item) => item.id !== id) : list;
  const locations = keep(campaign.locations, 'location').map((l) =>
    kind === 'location' ? { ...l, connections: l.connections.filter((c) => c !== id) } : l,
  );
  return {
    ...campaign,
    start_location_id:
      kind === 'location' && campaign.start_location_id === id
        ? (locations[0]?.id ?? '')
        : campaign.start_location_id,
    locations,
    factions: keep(campaign.factions, 'faction'),
    npcs: keep(campaign.npcs, 'npc').map((n) => ({
      ...n,
      location_id: kind === 'location' && n.location_id === id ? null : n.location_id,
      faction_id: kind === 'faction' && n.faction_id === id ? null : n.faction_id,
    })),
    beats: keep(campaign.beats, 'beat').map((b) => ({
      ...b,
      requires: kind === 'beat' ? b.requires.filter((r) => r !== id) : b.requires,
    })),
    facts: campaign.facts.map((f) => ({ ...f, about: f.about === id ? null : f.about })),
  };
}

/** Um texto de várias linhas vira a lista de linhas não vazias (as notas e as metas se escrevem uma por linha). */
export function toLines(text: string): string[] {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line !== '');
}

/** O contrário de `toLines`: a lista vira um texto, uma linha por item. */
export function fromLines(lines: readonly string[]): string {
  return lines.join('\n');
}
