import type {
  AttributeInfo,
  Character,
  GameStatus,
  NpcInfo,
  NpcView,
  RulesView,
  WeaponInfo,
} from '@contract/api_responses';

/** Valores iniciais do formulário de personagem: o padrão de cada atributo do sistema. */
export function attributeDefaults(rules: RulesView): Record<string, number> {
  return Object.fromEntries(rules.attributes.map((a) => [a.id, a.default]));
}

/** O valor dentro dos limites do atributo, arredondado. */
export function clampAttribute(attribute: AttributeInfo, value: number): number {
  return Math.min(attribute.max, Math.max(attribute.min, Math.round(value)));
}

/** Se o atributo pode subir (`1`) ou descer (`-1`) um ponto. */
export function canStep(attribute: AttributeInfo, value: number, delta: 1 | -1): boolean {
  return delta === 1 ? value < attribute.max : value > attribute.min;
}

/**
 * As armas que o personagem pode usar: a arma padrão do sistema (que ninguém precisa ter no inventário, os
 * punhos) primeiro, e depois as do inventário. O motor confere de novo; isto só evita botão inútil.
 */
export function usableWeapons(rules: RulesView, inventory: readonly string[]): WeaponInfo[] {
  const owned = new Set(inventory);
  const standard = rules.combat.default_weapon;
  const first = rules.weapons.filter((w) => w.id === standard);
  const rest = rules.weapons.filter((w) => w.id !== standard && owned.has(w.id));
  return [...first, ...rest];
}

/** Por que o personagem não pode gastar a ação principal agora. */
export type ActBlock = 'no-character' | 'over' | 'acted' | 'fallen';

export const ACT_BLOCK_TEXT: Record<ActBlock, string> = {
  'no-character': 'Crie um personagem para agir.',
  over: 'A partida terminou.',
  acted: 'Seu personagem já agiu neste turno. Espere os outros.',
  fallen: 'Seu personagem está fora de combate.',
};

/** O que decide se o personagem pode agir: ele, o turno, quem já agiu, o desfecho e as regras. */
export interface ActContext {
  character: Character | null;
  turn: number;
  /** `TableView.acted`: personagem -> turno em que agiu. */
  acted: Readonly<Record<string, number>>;
  status: GameStatus;
  rules: RulesView;
}

/** Por que o personagem não pode gastar a ação principal agora, ou `null` se pode. */
export function actBlock(context: ActContext): ActBlock | null {
  const { character, turn, acted, status, rules } = context;
  if (character === null) {
    return 'no-character';
  }
  if (status !== 'active') {
    return 'over';
  }
  if (acted[character.id] === turn) {
    return 'acted';
  }
  if (character.hp <= 0 && !rules.combat.fallen_can_act) {
    return 'fallen';
  }
  return null;
}

/** Um alvo possível de ataque, com o hp que o jogador pode ver. */
export interface AttackTarget {
  id: string;
  name: string;
  hp: number;
  maxHp: number;
  hostile: boolean;
}

/** NPCs presentes e de pé (o `olhar` do jogador): é só deles que o jogador comum vê o hp. */
export function attackTargets(
  present: readonly NpcInfo[],
  state: Readonly<Record<string, NpcView>>,
): AttackTarget[] {
  return present.flatMap((npc) => {
    const view = state[npc.id];
    return view?.alive === true && view.hp > 0
      ? [{ id: npc.id, name: npc.name, hp: view.hp, maxHp: view.max_hp, hostile: view.hostile }]
      : [];
  });
}

/** Troca os códigos de atributo de uma fórmula pelos nomes ("2d6 + FOR" vira "2d6 + Força"); o resto fica como está. */
export function humanizeFormula(
  formula: string,
  attributes: readonly { id: string; name: string }[],
): string {
  const names = new Map(attributes.map((a) => [a.id, a.name]));
  return formula.replace(/[A-Za-z_]\w*/g, (word) => names.get(word) ?? word);
}
