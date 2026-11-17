import type { Beat, Campaign, FactDef, Faction, Location, Npc } from '@contract/api_responses';
import { slugify, uniqueId } from './names';

/**
 * As edições de uma campanha no editor, como funções puras: cada uma devolve uma campanha nova e nunca muda a que
 * recebeu. O servidor é quem valida; aqui só se mantém a campanha coerente com o que o autor faz (renomear um id
 * atualiza as referências, remover um item tira o que apontava para ele).
 */

/** Os tipos de item que têm id e são citados por outros. */
export type ItemKind = 'location' | 'npc' | 'faction' | 'beat' | 'fact';

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

/** Um marco novo, sem requisitos nem condições (só se ativa e se conclui pelo anfitrião). */
export function beat(id: string, title: string): Beat {
  return {
    id,
    title,
    description: '',
    requires: [],
    activate_when: [],
    complete_when: [],
    private_notes: [],
  };
}

/** Um fato novo, sem assunto nem condição de revelar (só o anfitrião o revela). */
export function fact(id: string, text: string): FactDef {
  return { id, text, about: null, reveal_when: [] };
}

/** Todos os ids da campanha (de qualquer tipo): um id novo não pode repetir nenhum deles dentro do seu tipo. */
export function idsOf(campaign: Campaign, kind: ItemKind): string[] {
  const lists = {
    location: campaign.locations,
    npc: campaign.npcs,
    faction: campaign.factions,
    beat: campaign.beats,
    fact: campaign.facts,
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

/** Acrescenta um marco. */
export function addBeat(campaign: Campaign, title = 'Novo marco'): Campaign {
  const id = freeId(campaign, 'beat', title);
  return { ...campaign, beats: [...campaign.beats, beat(id, title)] };
}

/** Acrescenta um fato. */
export function addFact(campaign: Campaign, text = 'Novo fato'): Campaign {
  const id = freeId(campaign, 'fact', text);
  return { ...campaign, facts: [...campaign.facts, fact(id, text)] };
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
    facts: own(campaign.facts, 'fact').map((f) => ({
      ...f,
      about: f.about === null || kind === 'fact' ? f.about : swap(f.about), // `about` pode apontar para qualquer tipo; ids iguais em tipos diferentes são ambíguos
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
    facts: keep(campaign.facts, 'fact').map((f) => ({
      ...f,
      about: kind !== 'fact' && f.about === id ? null : f.about,
    })),
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

/** Uma condição de um marco ou de um fato (todas as de uma lista precisam valer). */
export type Condition = Beat['activate_when'][number];

/** O tipo de uma condição. */
export type ConditionKind = Condition['kind'];

/** Os tipos de condição, na ordem do menu, com a frase que o autor lê. */
export const CONDITION_KINDS: readonly { kind: ConditionKind; label: string }[] = [
  { kind: 'at_location', label: 'O grupo está em' },
  { kind: 'npc_down', label: 'Um NPC caiu' },
  { kind: 'beat_done', label: 'Um marco foi concluído' },
  { kind: 'turn_at_least', label: 'Chegou ao turno' },
  { kind: 'check_passed', label: 'Alguém passou num teste de' },
];

/** A condição padrão de um tipo: aponta para o primeiro item que existe (ou fica vazia, e o validador avisa). */
export function defaultCondition(
  kind: ConditionKind,
  campaign: Campaign,
  skillIds: readonly string[],
): Condition {
  switch (kind) {
    case 'at_location':
      return { kind, location_id: campaign.locations[0]?.id ?? '' };
    case 'npc_down':
      return { kind, npc_id: campaign.npcs[0]?.id ?? '' };
    case 'beat_done':
      return { kind, beat_id: campaign.beats[0]?.id ?? '' };
    case 'turn_at_least':
      return { kind, turn: 1 };
    case 'check_passed':
      return { kind, skill_id: skillIds[0] ?? '' };
  }
}

/** A que item uma condição aponta (o id), ou `null` para a de turno. */
export function conditionTarget(condition: Condition): string | null {
  switch (condition.kind) {
    case 'at_location':
      return condition.location_id;
    case 'npc_down':
      return condition.npc_id;
    case 'beat_done':
      return condition.beat_id;
    case 'check_passed':
      return condition.skill_id;
    case 'turn_at_least':
      return null;
  }
}

/** A mesma condição apontando para outro item (ou, na de turno, outro turno: `target` é o número escrito). */
export function withTarget(condition: Condition, target: string): Condition {
  switch (condition.kind) {
    case 'at_location':
      return { ...condition, location_id: target };
    case 'npc_down':
      return { ...condition, npc_id: target };
    case 'beat_done':
      return { ...condition, beat_id: target };
    case 'check_passed':
      return { ...condition, skill_id: target };
    case 'turn_at_least':
      return { ...condition, turn: Number(target) };
  }
}
