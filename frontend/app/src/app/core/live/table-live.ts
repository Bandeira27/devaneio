import { Injectable, inject } from '@angular/core';
import { ApiClient } from '../api/api-client';
import { LiveEnv, LiveFeed } from './live-feed';

function abortError(): DOMException {
  return new DOMException('abortado', 'AbortError');
}

/** Abre o fluxo ao vivo de uma mesa, ligando o laço à API, aos temporizadores e à visibilidade da aba. */
@Injectable({ providedIn: 'root' })
export class TableLive {
  private readonly api = inject(ApiClient);

  open(tableId: string, startRevision: number): LiveFeed {
    const env: LiveEnv = {
      fetchEvents: (query, signal) =>
        new Promise((resolve, reject) => {
          if (signal.aborted) {
            reject(abortError());
            return;
          }
          const onAbort = (): void => {
            subscription.unsubscribe();
            reject(abortError());
          };
          const subscription = this.api.events(tableId, query).subscribe({
            next: (view) => {
              signal.removeEventListener('abort', onAbort);
              resolve(view);
            },
            error: (error: unknown) => {
              signal.removeEventListener('abort', onAbort);
              reject(error);
            },
          });
          signal.addEventListener('abort', onAbort, { once: true });
        }),
      sleep: (ms, signal) =>
        new Promise((resolve, reject) => {
          if (signal.aborted) {
            reject(abortError());
            return;
          }
          const onAbort = (): void => {
            clearTimeout(timer);
            reject(abortError());
          };
          const timer = setTimeout(() => {
            signal.removeEventListener('abort', onAbort);
            resolve();
          }, ms);
          signal.addEventListener('abort', onAbort, { once: true });
        }),
      random: () => Math.random(),
      now: () => performance.now(),
      hidden: () => document.visibilityState === 'hidden',
      whenVisible: (signal) =>
        new Promise((resolve, reject) => {
          if (signal.aborted) {
            reject(abortError());
            return;
          }
          const onAbort = (): void => {
            document.removeEventListener('visibilitychange', onChange);
            reject(abortError());
          };
          const onChange = (): void => {
            if (document.visibilityState === 'visible') {
              document.removeEventListener('visibilitychange', onChange);
              signal.removeEventListener('abort', onAbort);
              resolve();
            }
          };
          document.addEventListener('visibilitychange', onChange);
          signal.addEventListener('abort', onAbort, { once: true });
        }),
    };
    return new LiveFeed(env, startRevision);
  }
}
