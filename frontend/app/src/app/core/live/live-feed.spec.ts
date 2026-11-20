import type { ChatMessageView, EventView, EventsView, TalkView } from '@contract/api_responses';
import type { EventsQuery } from '../api/api-types';
import { ApiFailure } from '../api/api-failure';
import {
  FAST_EMPTY_MS,
  INITIAL_WINDOW,
  LONG_POLL_SECONDS,
  LiveEnv,
  LiveFeed,
  MAX_EVENTS,
} from './live-feed';

function event(index: number, text = `evento ${index}`): EventView {
  return { index, turn: 0, kind: 'move', text, prose: text, narration: null, outcome: null };
}

function chatMessage(seq: number, text = `mensagem ${seq}`): ChatMessageView {
  return { seq, player_id: 'p2', name: 'Bia', role: 'player', text, at: 1_000 + seq };
}

function talk(seq: number): TalkView {
  return { seq, after: 0, to: 'aria', text: `fala ${seq}` };
}

function view(
  revision: number,
  events: EventView[] = [],
  talks: TalkView[] = [],
  talkSeq = 0,
  chat: ChatMessageView[] = [],
  chatSeq = 0,
): EventsView {
  return { revision, events, talk: talks, talk_seq: talkSeq, chat, chat_seq: chatSeq };
}

type Step = EventsView | Error | (() => Promise<EventsView>);

/** Ambiente falso: respostas roteirizadas, relógio manual e temporizadores que só registram. */
class FakeEnv implements LiveEnv {
  readonly queries: EventsQuery[] = [];
  readonly sleeps: number[] = [];
  clock = 0;
  isHidden = false;
  randomValue = 0.5; // sem jitter: fator 1
  readonly script: Step[];
  private visibleWaiters: (() => void)[] = [];
  elapsedPerFetch = 5000; // por padrão uma espera longa de verdade

  constructor(...script: Step[]) {
    this.script = script;
  }

  fetchEvents(query: EventsQuery, signal: AbortSignal): Promise<EventsView> {
    this.queries.push(query);
    const step = this.script.shift();
    if (step === undefined) {
      return new Promise((_resolve, reject) => {
        signal.addEventListener('abort', () => reject(new DOMException('abortado', 'AbortError')));
      });
    }
    this.clock += this.elapsedPerFetch;
    if (typeof step === 'function') {
      return step();
    }
    return step instanceof Error ? Promise.reject(step) : Promise.resolve(step);
  }

  sleep(ms: number): Promise<void> {
    this.sleeps.push(ms);
    return Promise.resolve();
  }

  random(): number {
    return this.randomValue;
  }

  now(): number {
    return this.clock;
  }

  hidden(): boolean {
    return this.isHidden;
  }

  whenVisible(signal: AbortSignal): Promise<void> {
    return new Promise((resolve, reject) => {
      this.visibleWaiters.push(resolve);
      signal.addEventListener('abort', () => reject(new DOMException('abortado', 'AbortError')));
    });
  }

  show(): void {
    this.isHidden = false;
    this.visibleWaiters.splice(0).forEach((resolve) => resolve());
  }
}

const network = (): ApiFailure => new ApiFailure(0, 'network', 'Sem conexão.');

describe('LiveFeed', () => {
  async function drain(feed: LiveFeed, env: FakeEnv, expectedQueries: number): Promise<void> {
    await vi.waitFor(() => expect(env.queries.length).toBeGreaterThanOrEqual(expectedQueries));
    await vi.waitFor(() => expect(feed.status()).not.toBe('connecting'));
  }

  it('a primeira chamada não espera e começa na janela inicial; as seguintes esperam 20 s', async () => {
    const env = new FakeEnv(view(120, [event(70)]), view(121, [event(120)]));
    const feed = new LiveFeed(env, 120);
    const done = feed.run();
    await drain(feed, env, 3);
    expect(env.queries[0]).toEqual({
      since: 120 - INITIAL_WINDOW,
      sinceTalk: 0,
      sinceChat: 0,
      wait: 0,
    });
    expect(env.queries[1]).toEqual({
      since: 120,
      sinceTalk: 0,
      sinceChat: 0,
      wait: LONG_POLL_SECONDS,
    });
    expect(env.queries[2]).toEqual({
      since: 121,
      sinceTalk: 0,
      sinceChat: 0,
      wait: LONG_POLL_SECONDS,
    });
    feed.stop();
    await done;
  });

  it('a janela inicial nunca fica negativa', async () => {
    const env = new FakeEnv(view(3));
    const feed = new LiveFeed(env, 3);
    const done = feed.run();
    await drain(feed, env, 2);
    expect(env.queries[0]?.since).toBe(0);
    feed.stop();
    await done;
  });

  it('junta os eventos novos em ordem e sem repetir o que já tem', async () => {
    const env = new FakeEnv(view(2, [event(0), event(1)]), view(4, [event(1), event(2), event(3)]));
    const feed = new LiveFeed(env, 2);
    const done = feed.run();
    await drain(feed, env, 3);
    expect(feed.events().map((e) => e.index)).toEqual([0, 1, 2, 3]);
    expect(feed.revision()).toBe(4);
    feed.stop();
    await done;
  });

  it('guarda a revisão e não o último índice (o jogador comum recebe eventos com buracos)', async () => {
    const env = new FakeEnv(view(10, [event(2), event(7)]));
    const feed = new LiveFeed(env, 10);
    const done = feed.run();
    await drain(feed, env, 2);
    expect(env.queries[1]?.since).toBe(10);
    feed.stop();
    await done;
  });

  it('devolve o talk_seq do mural e junta as falas sem repetir', async () => {
    const env = new FakeEnv(
      view(5, [], [talk(1000), talk(1001)], 1001),
      view(5, [], [talk(1001), talk(1002)], 1002),
    );
    const feed = new LiveFeed(env, 5);
    const done = feed.run();
    await drain(feed, env, 3);
    expect(env.queries[1]?.sinceTalk).toBe(1001);
    expect(env.queries[2]?.sinceTalk).toBe(1002);
    expect(feed.talk().map((t) => t.seq)).toEqual([1000, 1001, 1002]);
    feed.stop();
    await done;
  });

  it('o talk_seq nunca recua', async () => {
    const env = new FakeEnv(view(1, [], [], 500), view(1, [], [], 300));
    const feed = new LiveFeed(env, 1);
    const done = feed.run();
    await drain(feed, env, 3);
    expect(env.queries[2]?.sinceTalk).toBe(500);
    feed.stop();
    await done;
  });

  it(`mantém no máximo ${MAX_EVENTS} eventos, os mais novos`, async () => {
    const many = Array.from({ length: MAX_EVENTS + 30 }, (_, i) => event(i));
    const env = new FakeEnv(view(many.length, many));
    const feed = new LiveFeed(env, many.length);
    const done = feed.run();
    await drain(feed, env, 2);
    expect(feed.events()).toHaveLength(MAX_EVENTS);
    expect(feed.events()[0]?.index).toBe(30);
    expect(feed.events().at(-1)?.index).toBe(MAX_EVENTS + 29);
    feed.stop();
    await done;
  });

  it('fica "live" depois da primeira resposta', async () => {
    const env = new FakeEnv(view(1, [event(0)]));
    const feed = new LiveFeed(env, 1);
    expect(feed.status()).toBe('connecting');
    const done = feed.run();
    await drain(feed, env, 1);
    expect(feed.status()).toBe('live');
    feed.stop();
    await done;
  });

  describe('resposta vazia imediata (servidor sem vaga de espera)', () => {
    it('recua com tempo crescente em vez de girar sem parar', async () => {
      const env = new FakeEnv(view(1), view(1), view(1), view(1), view(1));
      env.elapsedPerFetch = 10; // volta na hora, sem mudança, com wait ligado
      const feed = new LiveFeed(env, 1);
      const done = feed.run();
      await vi.waitFor(() => expect(env.sleeps.length).toBeGreaterThanOrEqual(3));
      expect(env.sleeps.slice(0, 3)).toEqual([1000, 2000, 4000]);
      feed.stop();
      await done;
    });

    it('para de recuar assim que chega algo novo', async () => {
      const env = new FakeEnv(view(1), view(1), view(2, [event(1)]), view(2));
      env.elapsedPerFetch = 10;
      const feed = new LiveFeed(env, 1);
      const done = feed.run();
      await vi.waitFor(() => expect(env.queries.length).toBeGreaterThanOrEqual(5));
      expect(env.sleeps).toEqual([1000, 1000]); // a resposta com evento zerou a conta: o recuo recomeça em 1000, não 2000
      feed.stop();
      await done;
    });

    it(`uma espera longa de verdade (>= ${FAST_EMPTY_MS} ms) vazia não recua`, async () => {
      const env = new FakeEnv(view(1), view(1), view(1));
      const feed = new LiveFeed(env, 1);
      const done = feed.run();
      await vi.waitFor(() => expect(env.queries.length).toBeGreaterThanOrEqual(4));
      expect(env.sleeps).toEqual([]);
      feed.stop();
      await done;
    });
  });

  describe('erros', () => {
    it('rede fora: fica offline, recua com jitter e volta a "live"', async () => {
      const env = new FakeEnv(network(), network(), view(1, [event(0)]));
      env.randomValue = 0; // jitter mínimo: fator 0,8
      const feed = new LiveFeed(env, 1);
      const done = feed.run();
      await vi.waitFor(() => expect(feed.status()).toBe('live'));
      expect(env.sleeps).toEqual([800, 1600]);
      expect(feed.events()).toHaveLength(1);
      feed.stop();
      await done;
    });

    it('o recuo tem teto de 15 s (mais o jitter)', async () => {
      const env = new FakeEnv(...Array.from({ length: 8 }, network));
      env.randomValue = 1; // jitter máximo: fator 1,2
      const feed = new LiveFeed(env, 1);
      const done = feed.run();
      await vi.waitFor(() => expect(env.sleeps.length).toBeGreaterThanOrEqual(8));
      expect(Math.max(...env.sleeps)).toBe(18_000);
      expect(env.sleeps.slice(0, 4)).toEqual([1200, 2400, 4800, 9600]);
      feed.stop();
      await done;
    });

    it.each([429, 500, 502, 408])('o status %i é repetido depois de um recuo', async (status) => {
      const env = new FakeEnv(new ApiFailure(status, 'x', 'm'), view(1, [event(0)]));
      const feed = new LiveFeed(env, 1);
      const done = feed.run();
      await vi.waitFor(() => expect(feed.status()).toBe('live'));
      expect(env.sleeps).toHaveLength(1);
      feed.stop();
      await done;
    });

    it('401 encerra como "expired" e não chama de novo', async () => {
      const env = new FakeEnv(new ApiFailure(401, 'unauthorized', 'token'), view(1));
      const feed = new LiveFeed(env, 1);
      await feed.run();
      expect(feed.status()).toBe('expired');
      expect(env.queries).toHaveLength(1);
    });

    it('404 encerra como "gone" e não chama de novo', async () => {
      const env = new FakeEnv(new ApiFailure(404, 'table_not_found', 'sumiu'), view(1));
      const feed = new LiveFeed(env, 1);
      await feed.run();
      expect(feed.status()).toBe('gone');
      expect(env.queries).toHaveLength(1);
    });

    it.each([400, 403, 409, 422])(
      'o status %i (não repetível) encerra como "failed"',
      async (status) => {
        const env = new FakeEnv(new ApiFailure(status, 'x', 'm'), view(1));
        const feed = new LiveFeed(env, 1);
        await feed.run();
        expect(feed.status()).toBe('failed');
        expect(env.queries).toHaveLength(1);
      },
    );

    it('um erro que não é ApiFailure vira falha de rede e tenta de novo', async () => {
      const env = new FakeEnv(new TypeError('Failed to fetch'), view(1, [event(0)]));
      const feed = new LiveFeed(env, 1);
      const done = feed.run();
      await vi.waitFor(() => expect(feed.status()).toBe('live'));
      expect(env.sleeps).toHaveLength(1);
      feed.stop();
      await done;
    });

    it('depois de uma resposta boa o recuo recomeça do início', async () => {
      const env = new FakeEnv(network(), network(), view(1), network(), view(1));
      const feed = new LiveFeed(env, 1);
      const done = feed.run();
      await vi.waitFor(() => expect(env.queries.length).toBeGreaterThanOrEqual(6));
      expect(env.sleeps).toEqual([1000, 2000, 1000]);
      feed.stop();
      await done;
    });
  });

  describe('aba oculta', () => {
    it('não chama a API enquanto oculta e retoma na hora quando volta', async () => {
      const env = new FakeEnv(view(1, [event(0)]));
      env.script.push(() => {
        env.isHidden = true; // a aba some enquanto esta resposta chega
        return Promise.resolve(view(2, [event(1)]));
      });
      const feed = new LiveFeed(env, 1);
      const done = feed.run();
      await vi.waitFor(() => expect(feed.events()).toHaveLength(2));
      await new Promise((resolve) => setTimeout(resolve, 20));
      expect(env.queries).toHaveLength(2); // oculta: nenhuma chamada nova
      env.show();
      await vi.waitFor(() => expect(env.queries).toHaveLength(3));
      expect(env.sleeps).toEqual([]); // retomou sem recuo
      feed.stop();
      await done;
    });

    it('stop() destrava a espera pela aba visível', async () => {
      const env = new FakeEnv(view(1));
      env.isHidden = true;
      const feed = new LiveFeed(env, 1);
      const done = feed.run();
      await new Promise((resolve) => setTimeout(resolve, 10));
      expect(env.queries).toHaveLength(0);
      feed.stop();
      await done;
      expect(env.queries).toHaveLength(0);
    });
  });

  describe('chat', () => {
    it('guarda as mensagens, devolve a última posição e não repete as que já tem', async () => {
      const env = new FakeEnv(
        view(1, [], [], 0, [chatMessage(1), chatMessage(2)], 2),
        view(1, [], [], 0, [chatMessage(2), chatMessage(3)], 3),
      );
      const feed = new LiveFeed(env, 1);
      const done = feed.run();
      await drain(feed, env, 3);
      expect(feed.chat().map((m) => m.seq)).toEqual([1, 2, 3]);
      expect(env.queries[1]?.sinceChat).toBe(2);
      expect(env.queries[2]?.sinceChat).toBe(3);
      feed.stop();
      await done;
    });

    it('uma mensagem enviada por esta aba aparece já e a volta do long-poll não a repete', async () => {
      const env = new FakeEnv(view(1), view(1, [], [], 0, [chatMessage(1, 'oi')], 1));
      const feed = new LiveFeed(env, 1);
      feed.addChat(chatMessage(1, 'oi'));
      expect(feed.chat().map((m) => m.text)).toEqual(['oi']);
      const done = feed.run();
      await drain(feed, env, 3);
      expect(feed.chat()).toHaveLength(1);
      feed.stop();
      await done;
    });
  });

  describe('parar', () => {
    it('stop() aborta a espera em andamento e encerra o laço sem erro', async () => {
      const env = new FakeEnv(view(1));
      const feed = new LiveFeed(env, 1);
      const done = feed.run();
      await vi.waitFor(() => expect(env.queries.length).toBe(2)); // a 2ª ficou esperando
      feed.stop();
      await done;
      expect(env.queries).toHaveLength(2);
    });

    it('depois de parar não chama a API nem muda o estado', async () => {
      const env = new FakeEnv(view(1));
      const feed = new LiveFeed(env, 1);
      feed.stop();
      await feed.run();
      expect(env.queries).toHaveLength(0);
      expect(feed.status()).toBe('connecting');
    });
  });
});
