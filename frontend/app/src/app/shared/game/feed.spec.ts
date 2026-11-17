import type { EventView, TalkView } from '@contract/api_responses';
import {
  FADE_FLOOR,
  FADE_PER_TURN,
  ageFade,
  FeedEvent,
  FeedItem,
  FeedTalk,
  ageOpacity,
  buildFeed,
} from './feed';

function event(index: number, turn: number, over: Partial<EventView> = {}): EventView {
  return {
    index,
    turn,
    kind: 'move',
    text: `mecânica ${index}`,
    prose: `prosa ${index}`,
    narration: null,
    outcome: null,
    ...over,
  };
}

function talk(seq: number, after: number, text = `fala ${seq}`): TalkView {
  return { seq, after, to: 'aria', text };
}

const types = (items: FeedItem[]): string[] =>
  items.map((i) => (i.type === 'turn' ? `turno ${i.turn}` : i.key));

describe('ageFade', () => {
  it('vai de 0 (agora) a 1 (no piso), reescalado pelo piso', () => {
    expect(ageFade(0)).toBe(0);
    expect(ageFade(2)).toBe(0.57); // opacidade 0,8 de um piso de 0,65
    expect(ageFade(4)).toBe(1);
    expect(ageFade(50)).toBe(1);
  });
});

describe('ageOpacity', () => {
  it('a cena atual é nítida', () => {
    expect(ageOpacity(0)).toBe(1);
    expect(ageOpacity(-3)).toBe(1);
  });

  it('cai por turno e para no piso', () => {
    expect(ageOpacity(1)).toBe(1 - FADE_PER_TURN);
    expect(ageOpacity(2)).toBe(0.8);
    expect(ageOpacity(3)).toBe(0.7);
    expect(ageOpacity(4)).toBe(FADE_FLOOR);
    expect(ageOpacity(50)).toBe(FADE_FLOOR);
  });

  it('respeita um piso diferente', () => {
    expect(ageOpacity(50, 0.8)).toBe(0.8);
  });
});

describe('buildFeed', () => {
  it('põe um divisor de turno antes do primeiro evento de cada turno', () => {
    const feed = buildFeed([event(0, 1), event(1, 1), event(2, 2)], [], 2);
    expect(types(feed)).toEqual(['turno 1', 'event-0', 'event-1', 'turno 2', 'event-2']);
    expect(
      feed.filter((i) => i.type === 'turn').map((i) => (i.type === 'turn' ? i.current : null)),
    ).toEqual([false, true]);
  });

  it('ordena por índice mesmo se vier fora de ordem e aceita buracos', () => {
    const feed = buildFeed([event(7, 2), event(2, 1), event(5, 1)], [], 2);
    expect(feed.filter((i) => i.type === 'event').map((i) => (i as FeedEvent).index)).toEqual([
      2, 5, 7,
    ]);
  });

  it('mostra a narração do LLM quando existe e a prosa da gramática no resto', () => {
    const [, first, second] = buildFeed(
      [event(0, 1, { narration: 'O vento muda.' }), event(1, 1)],
      [],
      1,
    ) as [FeedItem, FeedEvent, FeedEvent];
    expect(first.narration).toBe('O vento muda.');
    expect(first.note).toBe('mecânica 0');
    expect(second.narration).toBe('prosa 1');
  });

  it('desbota os turnos passados e mantém a cena atual nítida', () => {
    const feed = buildFeed([event(0, 1), event(1, 3), event(2, 8)], [], 8);
    const fades = feed.filter((i): i is FeedEvent => i.type === 'event').map((i) => i.fade);
    expect(fades).toEqual([1, 1, 0]);
  });

  it('o piso vale para qualquer idade', () => {
    const feed = buildFeed([event(0, 0)], [], 100);
    expect((feed[1] as FeedEvent).fade).toBe(1);
  });

  it('marca o tom: dano, cura e descanso se destacam', () => {
    const feed = buildFeed(
      [
        event(0, 1, { kind: 'damage' }),
        event(1, 1, { kind: 'heal' }),
        event(2, 1, { kind: 'rest' }),
        event(3, 1),
      ],
      [],
      1,
    );
    expect(feed.filter((i): i is FeedEvent => i.type === 'event').map((i) => i.tone)).toEqual([
      'danger',
      'good',
      'good',
      'neutral',
    ]);
  });

  describe('falas do mestre', () => {
    it('entram depois do evento que as precedeu (after é a revisão na hora)', () => {
      // after = 2: a fala veio quando já existiam os eventos de índice 0 e 1
      const feed = buildFeed([event(0, 1), event(1, 1), event(2, 1)], [talk(1000, 2)], 1);
      expect(types(feed)).toEqual(['turno 1', 'event-0', 'event-1', 'talk-1000', 'event-2']);
    });

    it('as que vieram antes de qualquer evento abrem o fluxo', () => {
      const feed = buildFeed([event(0, 1)], [talk(1000, 0)], 1);
      expect(types(feed)).toEqual(['talk-1000', 'turno 1', 'event-0']);
    });

    it('as mais novas que todos os eventos ficam no fim, em ordem de seq', () => {
      const feed = buildFeed([event(0, 1)], [talk(1002, 5), talk(1001, 5)], 1);
      expect(types(feed)).toEqual(['turno 1', 'event-0', 'talk-1001', 'talk-1002']);
    });

    it('a fala desbota como o evento que a precedeu', () => {
      const feed = buildFeed([event(0, 1), event(1, 6)], [talk(1000, 1), talk(1001, 2)], 6);
      const talks = feed.filter((i): i is FeedTalk => i.type === 'talk');
      expect(talks.map((t) => t.fade)).toEqual([1, 0]);
    });

    it('só falas, sem eventos', () => {
      expect(types(buildFeed([], [talk(1, 0), talk(2, 0)], 1))).toEqual(['talk-1', 'talk-2']);
    });

    it('não altera as listas de entrada', () => {
      const events = [event(1, 1), event(0, 1)];
      const talks = [talk(2, 1), talk(1, 0)];
      buildFeed(events, talks, 1);
      expect(events.map((e) => e.index)).toEqual([1, 0]);
      expect(talks.map((t) => t.seq)).toEqual([2, 1]);
    });
  });

  it('um feed vazio é uma lista vazia', () => {
    expect(buildFeed([], [], 1)).toEqual([]);
  });

  it('as chaves são únicas (para o track do @for)', () => {
    const feed = buildFeed([event(0, 1), event(1, 2), event(2, 2)], [talk(1, 1), talk(2, 2)], 2);
    const keys = feed.map((i) => i.key);
    expect(new Set(keys).size).toBe(keys.length);
  });
});
