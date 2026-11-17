import type { BeatStatus, Campaign, CampaignView, GameState } from '@contract/api_responses';

/**
 * O que só o anfitrião vê da campanha: marcos, fatos, NPCs e locais com o estado da partida junto. Tudo é derivado
 * da `Campaign` inteira e do `GameState` inteiro; o servidor é quem decide o que cada papel recebe.
 */

/** Um marco com o seu estado e os requisitos já com o nome e o status. */
export interface BeatRow {
  id: string;
  title: string;
  description: string;
  status: BeatStatus;
  requires: { id: string; title: string; done: boolean }[];
  notes: string[];
  /** Por que `Ativar` não vale agora (texto), ou `''` se vale. */
  activateBlock: string;
  /** Por que `Concluir` e `Falhar` não valem agora (texto), ou `''` se valem. */
  finishBlock: string;
}

/** Um fato da campanha; `revealedTurn` é `null` enquanto está oculto. */
export interface FactRow {
  id: string;
  text: string;
  /** O nome de quem o fato fala, se houver. */
  about: string | null;
  revealedTurn: number | null;
}

/** Um NPC com o estado atual. */
export interface NpcRow {
  id: string;
  name: string;
  description: string;
  location: string;
  hp: number;
  maxHp: number;
  alive: boolean;
  disposition: number;
  notes: string[];
}

/** Um local; `current` é onde o grupo está. */
export interface LocationRow {
  id: string;
  name: string;
  description: string;
  current: boolean;
  notes: string[];
}

/** Quem pode ser alvo de `ferir` e `curar`: personagens e NPCs. */
export interface ToolTarget {
  id: string;
  name: string;
  kind: 'character' | 'npc';
}

/** A visão do anfitrião sobre a mesa. */
export interface HostView {
  beats: BeatRow[];
  facts: FactRow[];
  npcs: NpcRow[];
  locations: LocationRow[];
  targets: ToolTarget[];
}

/** A campanha inteira (a do anfitrião), e não a visão resumida do jogador. */
export function isFullCampaign(campaign: Campaign | CampaignView | null): campaign is Campaign {
  return campaign !== null && 'locations' in campaign;
}

const STATUS_TEXT: Record<BeatStatus, string> = {
  pending: 'pendente',
  active: 'ativo',
  done: 'concluído',
  failed: 'falhou',
};

/** O status de um marco em palavras. */
export function beatStatusText(status: BeatStatus): string {
  return STATUS_TEXT[status];
}

/** Monta a visão do anfitrião; `null` enquanto a campanha ou o estado inteiros não chegaram. */
export function hostViewOf(
  campaign: Campaign | CampaignView | null,
  state: GameState | { rng_seed?: undefined } | null,
): HostView | null {
  if (!isFullCampaign(campaign) || state === null || !('rng_seed' in state)) {
    return null;
  }
  const full = state as GameState;
  const beatTitle = new Map(campaign.beats.map((b) => [b.id, b.title]));
  const npcName = new Map(campaign.npcs.map((n) => [n.id, n.name]));
  const locationName = new Map(campaign.locations.map((l) => [l.id, l.name]));
  const status = (id: string): BeatStatus => full.beats[id] ?? 'pending';

  const beats = campaign.beats.map<BeatRow>((beat) => {
    const requires = beat.requires.map((id) => ({
      id,
      title: beatTitle.get(id) ?? id,
      done: status(id) === 'done',
    }));
    const current = status(beat.id);
    const missing = requires.filter((r) => !r.done).map((r) => r.title);
    return {
      id: beat.id,
      title: beat.title,
      description: beat.description,
      status: current,
      requires,
      notes: beat.private_notes,
      activateBlock:
        current !== 'pending'
          ? `Este marco está ${beatStatusText(current)}.`
          : missing.length > 0
            ? `Falta concluir: ${missing.join(', ')}.`
            : '',
      finishBlock:
        current === 'active'
          ? ''
          : `Só um marco ativo pode ser concluído ou falhar; este está ${beatStatusText(current)}.`,
    };
  });

  const facts = campaign.facts.map<FactRow>((fact) => ({
    id: fact.id,
    text: fact.text,
    about: fact.about ? (npcName.get(fact.about) ?? fact.about) : null,
    revealedTurn: full.revealed_facts[fact.id] ?? null,
  }));

  const npcs = campaign.npcs.map<NpcRow>((npc) => {
    const now = full.npcs[npc.id];
    return {
      id: npc.id,
      name: npc.name,
      description: npc.description,
      location: now?.location_id
        ? (locationName.get(now.location_id) ?? now.location_id)
        : 'sem local',
      hp: now?.hp ?? 0,
      maxHp: now?.max_hp ?? 0,
      alive: now?.alive ?? false,
      disposition: now?.disposition ?? npc.disposition,
      notes: npc.private_notes,
    };
  });

  const locations = campaign.locations.map<LocationRow>((location) => ({
    id: location.id,
    name: location.name,
    description: location.description,
    current: location.id === full.current_location_id,
    notes: location.private_notes,
  }));

  const targets: ToolTarget[] = [
    ...Object.values(full.characters).map<ToolTarget>((c) => ({
      id: c.id,
      name: c.name,
      kind: 'character',
    })),
    ...npcs
      .filter((n) => n.alive)
      .map<ToolTarget>((n) => ({ id: n.id, name: n.name, kind: 'npc' })),
  ];

  return { beats, facts, npcs, locations, targets };
}
