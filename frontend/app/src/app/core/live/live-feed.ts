import { signal } from '@angular/core';
import type { EventView, EventsView, TalkView } from '@contract/api_responses';
import type { EventsQuery } from '../api/api-types';
import { ApiFailure } from '../api/api-failure';
import { backoffDelay } from './live-backoff';
import { MAX_EVENTS, MAX_TALK, mergeEvents, mergeTalk } from './live-merge';

export { MAX_EVENTS, MAX_TALK };

export type LiveStatus = 'connecting' | 'live' | 'offline' | 'expired' | 'gone' | 'failed';

/** Tudo que o laço pede ao mundo: assim ele é testável sem rede, sem relógio e sem DOM. */
export interface LiveEnv {
  fetchEvents(query: EventsQuery, signal: AbortSignal): Promise<EventsView>;
  sleep(ms: number, signal: AbortSignal): Promise<void>;
  random(): number;
  now(): number;
  hidden(): boolean;
  whenVisible(signal: AbortSignal): Promise<void>;
}

/** Quantos eventos antes da revisão atual entram na carga inicial (histórico mais antigo fica de fora). */
export const INITIAL_WINDOW = 50;
/** `wait` do long-poll: menor que o teto de 30 s do servidor, para a espera presa de uma aba que sumiu durar pouco. */
export const LONG_POLL_SECONDS = 20;
/** Resposta vazia mais rápida que isto, com `wait` ligado, é o servidor sem vaga de espera: não dá para girar. */
export const FAST_EMPTY_MS = 1000;

/**
 * O fluxo ao vivo de uma mesa: um laço de long-poll por aba. Primeira chamada sem espera (carrega a janela
 * inicial e o mural), depois `wait` de 20 s. Guarda a `revision` (não `index + 1`: o jogador comum recebe
 * eventos com buracos) e o `talk_seq`. Erro de rede e do servidor recuam com jitter; 401 e 404 encerram.
 */
export class LiveFeed {
  readonly status = signal<LiveStatus>('connecting');
  readonly events = signal<EventView[]>([]);
  readonly talk = signal<TalkView[]>([]);
  readonly revision = signal(0);

  private since: number;
  private sinceTalk = 0;
  private first = true;
  private readonly abort = new AbortController();

  constructor(
    private readonly env: LiveEnv,
    startRevision: number,
  ) {
    this.since = Math.max(0, startRevision - INITIAL_WINDOW);
    this.revision.set(startRevision);
  }

  /** Roda o laço até `stop()`, 401, 404 ou erro que não adianta repetir. */
  async run(): Promise<void> {
    const signal = this.abort.signal;
    let failures = 0;
    let quick = 0;
    while (!signal.aborted) {
      if (this.env.hidden()) {
        await this.env.whenVisible(signal).catch(() => undefined);
        continue; // reavalia: a aba pode ter sido fechada ou escondida de novo
      }
      const wait = this.first ? 0 : LONG_POLL_SECONDS;
      const started = this.env.now();
      let view: EventsView;
      try {
        view = await this.env.fetchEvents(
          { since: this.since, sinceTalk: this.sinceTalk, wait },
          signal,
        );
      } catch (error) {
        if (signal.aborted) {
          break;
        }
        const failure =
          error instanceof ApiFailure ? error : new ApiFailure(0, 'network', 'Sem conexão.');
        if (failure.status === 401) {
          this.status.set('expired');
          break;
        }
        if (failure.status === 404) {
          this.status.set('gone');
          break;
        }
        if (!failure.retryable) {
          this.status.set('failed');
          break;
        }
        this.status.set('offline');
        await this.env.sleep(this.delay(failures++), signal).catch(() => undefined);
        continue;
      }
      failures = 0;
      this.first = false;
      this.status.set('live');
      const changed = this.apply(view);
      if (!changed && wait > 0 && this.env.now() - started < FAST_EMPTY_MS) {
        await this.env.sleep(this.delay(quick++), signal).catch(() => undefined);
      } else {
        quick = 0;
      }
    }
  }

  stop(): void {
    this.abort.abort();
  }

  private apply(view: EventsView): boolean {
    const events = mergeEvents(this.events(), view.events);
    const talk = mergeTalk(this.talk(), view.talk);
    if (events !== null) {
      this.events.set(events);
    }
    if (talk !== null) {
      this.talk.set(talk);
    }
    const moved = view.revision !== this.revision();
    this.revision.set(view.revision);
    this.since = view.revision;
    this.sinceTalk = Math.max(this.sinceTalk, view.talk_seq);
    return events !== null || talk !== null || moved;
  }

  private delay(attempt: number): number {
    return backoffDelay(attempt, this.env.random());
  }
}
