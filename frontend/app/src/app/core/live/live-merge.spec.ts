import type { EventView, TalkView } from '@contract/api_responses';
import { MAX_EVENTS, MAX_TALK, mergeEvents, mergeTalk } from './live-merge';

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
