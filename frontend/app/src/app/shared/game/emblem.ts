import type { IconName } from '../ui/icon/icon';

/** O emblema de uma campanha: o ícone e o tom (o papel de cor em `tokens.css`) que a distinguem na lista. */
export interface Emblem {
  icon: IconName;
  tone: 'accent' | 'info' | 'ok' | 'warn';
}

const ICONS: readonly IconName[] = ['book', 'map', 'flag', 'scroll', 'eye', 'person'];
const TONES: readonly Emblem['tone'][] = ['accent', 'info', 'ok', 'warn'];

/**
 * O emblema de uma campanha, sempre o mesmo para o mesmo id (a campanha só tem id, título e premissa: não há ícone
 * escolhido por quem a escreveu). Um hash simples do id escolhe o ícone e o tom, de conjuntos fechados.
 */
export function campaignEmblem(id: string): Emblem {
  let hash = 0;
  for (const char of id) {
    hash = (hash * 31 + (char.codePointAt(0) ?? 0)) >>> 0;
  }
  return {
    icon: ICONS[hash % ICONS.length] ?? 'book',
    tone: TONES[Math.floor(hash / ICONS.length) % TONES.length] ?? 'accent',
  };
}
