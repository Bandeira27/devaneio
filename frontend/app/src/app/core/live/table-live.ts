import { Injectable, inject } from '@angular/core';
import { ApiClient } from '../api/api-client';
import { abortable } from './abortable';
import { LiveEnv, LiveFeed } from './live-feed';

/** Abre o fluxo ao vivo de uma mesa, ligando o laço à API, aos temporizadores e à visibilidade da aba. */
@Injectable({ providedIn: 'root' })
export class TableLive {
  private readonly api = inject(ApiClient);

  open(tableId: string, startRevision: number): LiveFeed {
    const env: LiveEnv = {
      fetchEvents: (query, signal) =>
        abortable(signal, (resolve, reject) => {
          const subscription = this.api.events(tableId, query).subscribe({
            next: resolve,
            error: reject,
          });
          return () => subscription.unsubscribe();
        }),
      sleep: (ms, signal) =>
        abortable<undefined>(signal, (resolve) => {
          const timer = setTimeout(() => resolve(undefined), ms);
          return () => clearTimeout(timer);
        }),
      random: () => Math.random(),
      now: () => performance.now(),
      hidden: () => document.visibilityState === 'hidden',
      whenVisible: (signal) =>
        abortable<undefined>(signal, (resolve) => {
          const onChange = (): void => {
            if (document.visibilityState === 'visible') {
              document.removeEventListener('visibilitychange', onChange);
              resolve(undefined);
            }
          };
          document.addEventListener('visibilitychange', onChange);
          return () => document.removeEventListener('visibilitychange', onChange);
        }),
    };
    return new LiveFeed(env, startRevision);
  }
}
