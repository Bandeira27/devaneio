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
  /**
   * O id da campanha da mesa, para agrupar as mesas por campanha. Falta nas mesas guardadas antes dele existir: elas
   * casam pelo título até serem abertas de novo (a mesa carregada o grava).
   */
  campaignId?: string;
  /** Só do anfitrião: o código de convite, para mostrar o link de novo. */
  invite?: string;
  savedAt: number;
}

export const TABLE_ID = /^[a-f0-9]{16}$/;
const PLAYER_ID = /^p\d{1,3}$/;
const CAMPAIGN_ID = /^[a-z0-9][a-z0-9_-]*$/;

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
    (v['campaignId'] === undefined ||
      (typeof v['campaignId'] === 'string' && CAMPAIGN_ID.test(v['campaignId']))) &&
    (v['invite'] === undefined || (typeof v['invite'] === 'string' && v['invite'].length <= 100)) &&
    typeof v['savedAt'] === 'number' &&
    Number.isFinite(v['savedAt'])
  );
}
