import type { ChatMessageView, EventView, TalkView } from '@contract/api_responses';
import {
  MAX_CHAT_KEPT,
  MAX_EVENTS,
  MAX_TALK,
  mergeChat,
  mergeEvents,
  mergeTalk,
} from './live-merge';

const event = (index: number): EventView => ({
  index,
  turn: 0,
  kind: 'move',
  text: `t${index}`,
  prose: `p${index}`,
  narration: null,
  outcome: null,
});
const talk = (seq: number): TalkView => ({ seq, after: 0, to: 'bia', text: `f${seq}` });

describe('mergeEvents', () => {
  it('acrescenta o novo, ordena por índice e ignora o repetido', () => {
    const merged = mergeEvents([event(1), event(4)], [event(3), event(4)]);
    expect(merged?.map((e) => e.index)).toEqual([1, 3, 4]);
  });

  it('devolve null quando não há nada novo', () => {
    expect(mergeEvents([event(1)], [event(1)])).toBeNull();
    expect(mergeEvents([], [])).toBeNull();
  });

  it('guarda só os mais recentes', () => {
    const many = Array.from({ length: MAX_EVENTS + 5 }, (_, i) => event(i));
    const merged = mergeEvents([], many) ?? [];
    expect(merged).toHaveLength(MAX_EVENTS);
    expect(merged[0]?.index).toBe(5);
  });
});

describe('mergeTalk', () => {
  it('ordena por seq e corta no máximo', () => {
    const many = Array.from({ length: MAX_TALK + 3 }, (_, i) => talk(MAX_TALK + 3 - i));
    const merged = mergeTalk([], many) ?? [];
    expect(merged).toHaveLength(MAX_TALK);
    expect(merged.at(-1)?.seq).toBe(MAX_TALK + 3);
  });
});

describe('mergeChat', () => {
  const message = (seq: number): ChatMessageView => ({
    seq,
    player_id: 'p1',
    name: 'Ana',
    role: 'host',
    text: `m${seq}`,
    at: seq,
  });

  it('ordena por seq, ignora a repetida e devolve null sem novidade', () => {
    expect(
      mergeChat([message(1), message(4)], [message(3), message(4)])?.map((m) => m.seq),
    ).toEqual([1, 3, 4]);
    expect(mergeChat([message(1)], [message(1)])).toBeNull();
  });

  it('guarda só as mais recentes', () => {
    const many = Array.from({ length: MAX_CHAT_KEPT + 4 }, (_, i) => message(i + 1));
    const merged = mergeChat([], many) ?? [];
    expect(merged).toHaveLength(MAX_CHAT_KEPT);
    expect(merged[0]?.seq).toBe(5);
  });
});
