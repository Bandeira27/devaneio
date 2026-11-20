import type { ArchivedTable, EditorTable } from '@contract/api_responses';
import { whenOf } from './when';

const PHASE = {
  lobby: 'na sala de espera',
  running: 'em jogo',
  paused: 'pausada',
  ended: 'encerrada',
} as const;

const playersOf = (table: EditorTable | ArchivedTable): string =>
  `${table.players} ${table.players === 1 ? 'jogador' : 'jogadores'}`;

/** O nome da mesa, que é texto livre do anfitrião: "Mesa de Ana" (ou só "Mesa" sem anfitrião). */
export function tableName(table: EditorTable | ArchivedTable): string {
  return table.host_name === '' ? 'Mesa' : `Mesa de ${table.host_name}`;
}

/** O resto da linha da mesa, que tem tamanho previsível: "em jogo · 2 jogadores · ontem". */
export function tableDetails(table: EditorTable, now: number): string {
  return `${PHASE[table.phase]} · ${playersOf(table)} · ${whenOf(table.updated_at * 1000, now)}`;
}

/** O resto da linha da mesa arquivada: "em jogo · 2 jogadores · jogada pela última vez ontem · arquivada ontem". */
export function archivedDetails(table: ArchivedTable, now: number): string {
  const archived = whenOf(table.archived_at * 1000, now);
  const played = whenOf(table.updated_at * 1000, now);
  return `${PHASE[table.phase]} · ${playersOf(table)} · jogada pela última vez ${played} · arquivada ${archived}`;
}

/** A mesa em uma linha, no vocabulário do jogo: "Mesa de Ana · em jogo · 2 jogadores · ontem". */
export function tableLine(table: EditorTable, now: number): string {
  return `${tableName(table)} · ${tableDetails(table, now)}`;
}

/** A mesa arquivada em uma linha: "Mesa de Ana · em jogo · 2 jogadores · jogada pela última vez ontem · arquivada ontem". */
export function archivedLine(table: ArchivedTable, now: number): string {
  return `${tableName(table)} · ${archivedDetails(table, now)}`;
}

/** O que a folha de confirmar diz ao arquivar uma mesa. */
export const ARCHIVE_TABLE_CONFIRM = {
  title: 'Arquivar esta mesa?',
  text: 'A mesa sai do jogo e da lista, para todos os jogadores. O histórico fica guardado no servidor, e você pode restaurá-la quando quiser. Este navegador esquece o acesso dela: ao restaurar, o anfitrião reabre por “Assumir como anfitrião”.',
  action: 'Arquivar a mesa',
};

/** O que a folha de confirmar diz ao apagar de vez uma mesa arquivada; `line` diz qual (`archivedLine`). */
export function purgeConfirm(line: string) {
  return {
    title: 'Apagar esta mesa de vez?',
    text: `${line}. A mesa e todo o histórico dela serão apagados do servidor. Isto não tem volta.`,
    action: 'Apagar de vez',
  };
}

/** O que a folha de confirmar diz ao assumir o lugar de anfitrião. */
export const ASSUME_HOST_CONFIRM = {
  title: 'Assumir como anfitrião?',
  text: 'Este navegador passa a ser o do anfitrião. O acesso e o convite antigos deixam de valer: quem já recebeu o link de convite precisa de um novo.',
  action: 'Assumir',
};
