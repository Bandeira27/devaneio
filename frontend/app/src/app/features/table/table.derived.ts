import type {
  Campaign,
  CampaignView,
  Character,
  GameState,
  NpcView,
  RulesView,
  TableView,
} from '@contract/api_responses';
import { ACT_BLOCK_TEXT, AttackTarget, actBlock, attackTargets } from '@shared/game/rules';
import { Scene, sceneOf } from '@shared/game/scene';

/** O personagem de quem está olhando (o primeiro do jogador), ou `null` se ainda não criou. */
export function characterOf(table: TableView | null): Character | null {
  const id = table?.players.find((p) => p.id === table.you)?.character_ids[0];
  return (id !== undefined ? table?.state.characters[id] : undefined) ?? null;
}

/** A cena em que o grupo está. O anfitrião vê os NPCs do estado completo; o jogador, só os da campanha pública. */
export function sceneFor(
  table: TableView | null,
  campaign: Campaign | CampaignView | null,
): Scene | null {
  if (table === null || campaign === null) {
    return null;
  }
  const hostNpcs = table.role === 'host' ? (table.state as GameState).npcs : {};
  return sceneOf(campaign, table.state.current_location_id, hostNpcs);
}

/** Por que o personagem não pode agir agora (texto), ou `''` se pode. */
export function blockedReasonOf(
  table: TableView | null,
  rules: RulesView | null,
  character: Character | null,
): string {
  if (table === null || rules === null) {
    return '';
  }
  const block = actBlock({
    character,
    turn: table.state.turn,
    acted: table.acted,
    status: table.status,
    rules,
  });
  return block === null ? '' : ACT_BLOCK_TEXT[block];
}

/** Quem dá para atacar na cena. */
export function targetsOf(table: TableView | null, scene: Scene | null): AttackTarget[] {
  if (table === null || scene === null) {
    return [];
  }
  const views: Record<string, NpcView> = {};
  for (const [id, npc] of Object.entries(table.state.npcs)) {
    // O anfitrião recebe o estado completo (sem `hostile`): só o jogador comum recebe a visão pronta.
    views[id] = {
      alive: npc.alive,
      hp: npc.hp,
      max_hp: npc.max_hp,
      hostile: 'hostile' in npc && npc.hostile,
    };
  }
  return attackTargets(scene.npcs, views);
}
