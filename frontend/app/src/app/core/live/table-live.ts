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
          const subscription = this.api.events(tableId, query).subscribe({
            next: resolve,
            error: reject,
          });
          signal.addEventListener(
            'abort',
            () => {
              subscription.unsubscribe();
              reject(abortError());
            },
            { once: true },
          );
        }),
      sleep: (ms, signal) =>
        new Promise((resolve, reject) => {
          const timer = setTimeout(resolve, ms);
          signal.addEventListener(
            'abort',
            () => {
              clearTimeout(timer);
              reject(abortError());
            },
            { once: true },
          );
        }),
      random: () => Math.random(),
      now: () => performance.now(),
      hidden: () => document.visibilityState === 'hidden',
      whenVisible: (signal) =>
        new Promise((resolve, reject) => {
          const onChange = (): void => {
            if (document.visibilityState === 'visible') {
              document.removeEventListener('visibilitychange', onChange);
              resolve();
            }
          };
          document.addEventListener('visibilitychange', onChange);
          signal.addEventListener(
            'abort',
            () => {
              document.removeEventListener('visibilitychange', onChange);
              reject(abortError());
            },
            { once: true },
          );
        }),
    };
    return new LiveFeed(env, startRevision);
  }
}
