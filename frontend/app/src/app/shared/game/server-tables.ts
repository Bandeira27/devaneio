import type { EditorTable } from '@contract/api_responses';
import { whenOf } from './when';

const PHASE = {
  lobby: 'na sala de espera',
  running: 'em jogo',
  paused: 'pausada',
  ended: 'encerrada',
} as const;

/** A mesa em uma linha, no vocabulário do jogo: "Mesa de Ana · em jogo · 2 jogadores · ontem". */
export function tableLine(table: EditorTable, now: number): string {
  const players = `${table.players} ${table.players === 1 ? 'jogador' : 'jogadores'}`;
  const host = table.host_name === '' ? 'Mesa' : `Mesa de ${table.host_name}`;
  return `${host} · ${PHASE[table.phase]} · ${players} · ${whenOf(table.updated_at * 1000, now)}`;
}

/** O que a folha de confirmar diz ao encerrar uma mesa. */
export const CLOSE_TABLE_CONFIRM = {
  title: 'Encerrar esta mesa?',
  text: 'A mesa e tudo o que aconteceu nela serão apagados do servidor, para todos os jogadores. Isto não tem volta.',
  action: 'Encerrar a mesa',
};

/** O que a folha de confirmar diz ao assumir o lugar de anfitrião. */
export const ASSUME_HOST_CONFIRM = {
  title: 'Assumir como anfitrião?',
  text: 'Este navegador passa a ser o do anfitrião. O acesso e o convite antigos deixam de valer: quem já recebeu o link de convite precisa de um novo.',
  action: 'Assumir',
};
