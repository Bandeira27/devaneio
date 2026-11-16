import type { EventView, TalkView } from '@contract/api_responses';

/** Piso de opacidade do que já passou: o desbotado nunca tira a leitura (tools/tokens.spec.ts confere). */
export const FADE_FLOOR = 0.65;
/** O quanto cada turno de idade desbota. */
export const FADE_PER_TURN = 0.1;

export type FeedTone = 'neutral' | 'danger' | 'good';

export interface FeedTurn {
  type: 'turn';
  key: string;
  turn: number;
  current: boolean;
}

export interface FeedEvent {
  type: 'event';
  key: string;
  index: number;
  turn: number;
  kind: string;
  /** O parágrafo do LLM se houver, senão a prosa da gramática. */
  narration: string;
  /** A linha mecânica, como nota de margem. */
  note: string;
  tone: FeedTone;
  opacity: number;
}

export interface FeedTalk {
  type: 'talk';
  key: string;
  seq: number;
  text: string;
  opacity: number;
}

export type FeedItem = FeedTurn | FeedEvent | FeedTalk;

const TONES: Record<string, FeedTone> = { damage: 'danger', heal: 'good', rest: 'good' };

/** Opacidade por idade em turnos: 1 na cena atual, cai `FADE_PER_TURN` por turno, nunca abaixo do piso. */
export function ageOpacity(age: number, floor = FADE_FLOOR): number {
  if (age <= 0) {
    return 1;
  }
  return Math.max(floor, Math.round((1 - age * FADE_PER_TURN) * 100) / 100);
}

/**
 * Eventos e falas do mestre num fluxo só: ordem dos eventos, cada fala logo depois do evento que a precedeu
 * (`after` é a revisão da mesa na hora), divisor a cada mudança de turno, e idade em turnos virando opacidade.
 */
export function buildFeed(
  events: readonly EventView[],
  talk: readonly TalkView[],
  currentTurn: number,
  floor = FADE_FLOOR,
): FeedItem[] {
  const ordered = [...events].sort((a, b) => a.index - b.index);
  const talks = [...talk].sort((a, b) => a.after - b.after || a.seq - b.seq);
  const items: FeedItem[] = [];
  let talkAt = 0;
  let lastTurn: number | null = null;
  let lastEventTurn = currentTurn;

  const flushTalk = (before: number): void => {
    while (talks[talkAt] !== undefined && (talks[talkAt]?.after ?? 0) <= before) {
      const t = talks[talkAt] as TalkView;
      items.push({
        type: 'talk',
        key: `talk-${t.seq}`,
        seq: t.seq,
        text: t.text,
        opacity: ageOpacity(currentTurn - lastEventTurn, floor),
      });
      talkAt++;
    }
  };

  for (const event of ordered) {
    flushTalk(event.index); // falas que vieram antes deste evento (after <= índice)
    if (event.turn !== lastTurn) {
      items.push({
        type: 'turn',
        key: `turn-${event.turn}-${event.index}`,
        turn: event.turn,
        current: event.turn === currentTurn,
      });
      lastTurn = event.turn;
    }
    lastEventTurn = event.turn;
    items.push({
      type: 'event',
      key: `event-${event.index}`,
      index: event.index,
      turn: event.turn,
      kind: event.kind,
      narration: event.narration ?? event.prose,
      note: event.text,
      tone: TONES[event.kind] ?? 'neutral',
      opacity: ageOpacity(currentTurn - event.turn, floor),
    });
  }
  flushTalk(Number.POSITIVE_INFINITY);
  return items;
}
