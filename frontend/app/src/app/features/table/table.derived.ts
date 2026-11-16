import type { LiveStatus } from '@core/live/live-feed';
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

/**
 * Por que a conexão impede agir agora (texto), ou `''` se está tudo certo. Sem a mesa ao vivo qualquer ação falharia
 * com um erro cru: melhor bloquear com o motivo.
 */
export function connectionBlockOf(status: LiveStatus): string {
  switch (status) {
    case 'offline':
      return 'Sem conexão com a mesa. Tentando de novo…';
    case 'expired':
      return 'Sua sessão nesta mesa não vale mais.';
    case 'gone':
      return 'Esta mesa não existe mais neste servidor.';
    case 'failed':
      return 'A conexão com a mesa falhou.';
    default:
      return '';
  }
}

/** Uma linha sobre a vez de quem olha: se pode agir, se já agiu e quem falta. */
export function turnStatusOf(table: TableView | null, character: Character | null): string {
  if (table === null) {
    return '';
  }
  if (table.status !== 'active') {
    return 'Partida encerrada';
  }
  if (character === null) {
    return 'Você ainda não tem personagem';
  }
  if (character.hp <= 0) {
    return 'Você está fora de combate';
  }
  const turn = table.state.turn;
  if (table.acted[character.id] !== turn) {
    return 'Sua vez de agir';
  }
  const waiting = Object.values(table.state.characters)
    .filter((c) => c.id !== character.id && c.hp > 0 && table.acted[c.id] !== turn)
    .map((c) => c.name);
  return waiting.length > 0 ? `Você já agiu · falta ${waiting.join(', ')}` : 'Você já agiu';
}
