/** Uma mesa em que este navegador entrou, como fica guardada, e a validação do que volta do armazenamento. */

/** Se quem guardou a mesa é o anfitrião ou um jogador. */
export type StoredRole = 'host' | 'player';

/** Uma mesa em que este navegador entrou, como fica guardada no armazenamento. */
export interface StoredTable {
  token: string;
  playerId: string;
  role: StoredRole;
  /** Título da campanha, para a lista de mesas guardadas. */
  title: string;
  /** Só do anfitrião: o código de convite, para mostrar o link de novo. */
  invite?: string;
  savedAt: number;
}

export const TABLE_ID = /^[a-f0-9]{16}$/;
const PLAYER_ID = /^p\d{1,3}$/;

/** Confere, campo a campo, que um valor lido do armazenamento tem o formato de uma `StoredTable`. */
export function isEntry(value: unknown): value is StoredTable {
  if (typeof value !== 'object' || value === null) {
    return false;
  }
  const v = value as Record<string, unknown>;
  return (
    typeof v['token'] === 'string' &&
    v['token'].length > 0 &&
    v['token'].length <= 200 &&
    typeof v['playerId'] === 'string' &&
    PLAYER_ID.test(v['playerId']) &&
    (v['role'] === 'host' || v['role'] === 'player') &&
    typeof v['title'] === 'string' &&
    v['title'].length <= 200 &&
    (v['invite'] === undefined || (typeof v['invite'] === 'string' && v['invite'].length <= 100)) &&
    typeof v['savedAt'] === 'number' &&
    Number.isFinite(v['savedAt'])
  );
}
