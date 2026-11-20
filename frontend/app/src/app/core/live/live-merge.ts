import type { ChatMessageView, EventView, TalkView } from '@contract/api_responses';

/** Quantos eventos e falas a tela guarda; os mais antigos saem primeiro. */
export const MAX_EVENTS = 200;
export const MAX_TALK = 50;
export const MAX_CHAT_KEPT = 200;

/**
 * Junta os itens novos aos já conhecidos: ignora os que já se conhece (pela chave), ordena e corta no máximo.
 *
 * @returns A lista nova, ou `null` se não havia nada novo (para quem chama não reescrever o sinal à toa).
 */
function mergeBy<T>(
  known: readonly T[],
  incoming: readonly T[],
  key: (item: T) => number,
  max: number,
): T[] | null {
  const seen = new Set(known.map(key));
  const fresh = incoming.filter((item) => !seen.has(key(item)));
  if (fresh.length === 0) {
    return null;
  }
  return [...known, ...fresh].sort((a, b) => key(a) - key(b)).slice(-max);
}

/** Junta eventos novos (a chave é o `index`), ou `null` se nenhum é novo. */
export function mergeEvents(known: readonly EventView[], incoming: readonly EventView[]) {
  return mergeBy(known, incoming, (event) => event.index, MAX_EVENTS);
}

/** Junta falas novas do mestre (a chave é o `seq`), ou `null` se nenhuma é nova. */
export function mergeTalk(known: readonly TalkView[], incoming: readonly TalkView[]) {
  return mergeBy(known, incoming, (talk) => talk.seq, MAX_TALK);
}

/** Junta mensagens novas do chat (a chave é o `seq`), ou `null` se nenhuma é nova. */
export function mergeChat(known: readonly ChatMessageView[], incoming: readonly ChatMessageView[]) {
  return mergeBy(known, incoming, (message) => message.seq, MAX_CHAT_KEPT);
}
