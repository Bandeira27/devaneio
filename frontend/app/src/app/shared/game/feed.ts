import type { EventView, TalkView } from '@contract/api_responses';
import type { BadgeTone } from '../ui/badge/badge';
import type { IconName } from '../ui/icon/icon';

/**
 * Piso de opacidade do texto de leitura que já passou: o desbotado nunca tira a leitura (`--dv-fade-floor-text`;
 * tools/tokens.spec.ts confere que é o mesmo no CSS).
 */
export const FADE_FLOOR = 0.65;
/** O quanto cada turno de idade desbota. */
export const FADE_PER_TURN = 0.1;

/** O tom de um evento no feed: normal, de dano ou de cura. */
export type FeedTone = 'neutral' | 'danger' | 'good';

/** O selo de desfecho de um evento: texto, tom e ícone (o desfecho nunca vai só na cor). */
export interface FeedSeal {
  label: string;
  tone: BadgeTone;
  icon: IconName;
}

/** O desfecho que o servidor entrega (`EventView.outcome`), sem o `null`. */
export type FeedOutcome = NonNullable<EventView['outcome']>;

const GOOD: Pick<FeedSeal, 'tone' | 'icon'> = { tone: 'ok', icon: 'ok' };
const BAD: Pick<FeedSeal, 'tone' | 'icon'> = { tone: 'danger', icon: 'danger' };

/** O selo de cada desfecho: teste, ataque, dano e cura. */
export const SEALS: Record<FeedOutcome, FeedSeal> = {
  critical_success: { label: 'Sucesso crítico', ...GOOD },
  success: { label: 'Sucesso', ...GOOD },
  failure: { label: 'Falha', ...BAD },
  critical_failure: { label: 'Falha crítica', ...BAD },
  critical_hit: { label: 'Acerto crítico', ...GOOD },
  hit: { label: 'Acerto', ...GOOD },
  miss: { label: 'Erro', ...BAD },
  critical_miss: { label: 'Erro crítico', ...BAD },
  damage: { label: 'Dano', ...BAD },
  incapacitated: { label: 'Fora de combate', ...BAD },
  heal: { label: 'Cura', ...GOOD },
};

/**
 * O que o motor escreve no fim da linha mecânica e o selo já diz: o grau de um teste (", sucesso crítico") e a queda
 * (", fora de combate"). Tirado da nota para o leitor de tela ouvir o desfecho uma vez só.
 */
const SEALED_SUFFIX = /, (?:sucesso crítico|sucesso|falha crítica|falha|fora de combate)$/;

/** O marcador de início de um turno. */
export interface FeedTurn {
  type: 'turn';
  key: string;
  turn: number;
  current: boolean;
}

/** Um evento do log, com a narração, a nota mecânica e o quanto já desbotou pela idade. */
export interface FeedEvent {
  type: 'event';
  key: string;
  index: number;
  turn: number;
  kind: string;
  /** O parágrafo do LLM se houver, senão a prosa da gramática. */
  narration: string;
  /** A linha mecânica, como nota de margem, sem o desfecho que o selo já diz. */
  note: string;
  /** O desfecho em selo, ou `null` onde o evento não tem um. */
  seal: FeedSeal | null;
  tone: FeedTone;
  /** De 0 (agora) a 1 (o mais antigo): cada papel do texto desbota até o seu piso (feed-list.css). */
  fade: number;
}

/** Uma fala do mestre ou de um NPC. */
export interface FeedTalk {
  type: 'talk';
  key: string;
  seq: number;
  text: string;
  /** De 0 (agora) a 1 (o mais antigo). */
  fade: number;
}

/** Um item do feed: marcador de turno, evento ou fala. */
export type FeedItem = FeedTurn | FeedEvent | FeedTalk;

const TONES: Record<string, FeedTone> = { damage: 'danger', heal: 'good', rest: 'good' };

/** Opacidade por idade em turnos: 1 na cena atual, cai `FADE_PER_TURN` por turno, nunca abaixo do piso. */
export function ageOpacity(age: number, floor = FADE_FLOOR): number {
  if (age <= 0) {
    return 1;
  }
  return Math.max(floor, Math.round((1 - age * FADE_PER_TURN) * 100) / 100);
}

/** O quanto já desbotou, de 0 (agora) a 1 (no piso): a opacidade que `ageOpacity` dá, reescalada pelo piso. */
export function ageFade(age: number): number {
  return Math.round(((1 - ageOpacity(age)) / (1 - FADE_FLOOR)) * 100) / 100;
}

/**
 * Eventos e falas do mestre num fluxo só: ordem dos eventos, cada fala logo depois do evento que a precedeu
 * (`after` é a revisão da mesa na hora), divisor a cada mudança de turno, e idade em turnos virando opacidade.
 */
export function buildFeed(
  events: readonly EventView[],
  talk: readonly TalkView[],
  currentTurn: number,
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
        fade: ageFade(currentTurn - lastEventTurn),
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
      note: event.outcome === null ? event.text : event.text.replace(SEALED_SUFFIX, ''),
      seal: event.outcome === null ? null : SEALS[event.outcome],
      tone: TONES[event.kind] ?? 'neutral',
      fade: ageFade(currentTurn - event.turn),
    });
  }
  flushTalk(Number.POSITIVE_INFINITY);
  return items;
}
