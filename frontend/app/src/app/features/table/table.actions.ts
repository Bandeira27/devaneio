import { signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { ApiClient } from '@core/api/api-client';
import { messageOf } from '@core/api/api-failure';
import { withStaleRetry } from '@core/api/stale-retry';
import type { TableSnapshot } from './table.snapshot';

/**
 * As ações do jogador na mesa: um comando em linha ou um texto livre para o mestre de IA. Uma de cada vez;
 * se a mesa andou (`stale_revision`) relê e repete uma vez, e ao terminar pede a foto nova da mesa.
 */
export class TableActions {
  /** Resposta que não gerou evento (`olhar`, `ficha`, a fala do mestre): aparece até a próxima ação. */
  readonly reply = signal('');
  readonly busy = signal(false);
  /** Verdadeiro só enquanto o mestre de IA pensa (texto livre); um comando comum não chama o LLM. */
  readonly thinking = signal(false);
  readonly error = signal('');
  /** O texto livre que está indo ao mestre, para a tela ecoar o que a pessoa disse enquanto ele pensa. */
  readonly saying = signal('');

  constructor(
    private readonly api: ApiClient,
    private readonly tableId: () => string,
    private readonly snapshot: TableSnapshot,
  ) {}

  /** Manda uma linha de comando; devolve se o servidor a aceitou. */
  run(line: string): Promise<boolean> {
    return this.act(async () => {
      const result = await this.send((revision) =>
        firstValueFrom(this.api.command(this.tableId(), { line, revision })),
      );
      this.reply.set(result.events.length === 0 ? result.text : '');
    });
  }

  /** Manda um texto livre; o servidor propõe e aplica as ações, ou só responde. */
  say(text: string): Promise<boolean> {
    return this.act(async () => {
      this.thinking.set(true);
      this.saying.set(text);
      const result = await this.send((revision) =>
        firstValueFrom(this.api.say(this.tableId(), { text, revision })),
      );
      this.reply.set(result.events.length === 0 ? result.say : '');
    });
  }

  private send<T>(request: (revision: number) => Promise<T>): Promise<T> {
    return withStaleRetry(
      request,
      () => this.snapshot.revision(),
      () => this.snapshot.refresh(),
    );
  }

  private async act(work: () => Promise<void>): Promise<boolean> {
    if (this.busy()) {
      return false;
    }
    this.busy.set(true);
    this.error.set('');
    this.reply.set('');
    try {
      await work();
      void this.snapshot.refresh();
      return true;
    } catch (error) {
      this.error.set(messageOf(error));
      return false;
    } finally {
      this.thinking.set(false);
      this.saying.set('');
      this.busy.set(false);
    }
  }

  /** Tira da tela a resposta e o erro da última ação. */
  dismiss(): void {
    this.reply.set('');
    this.error.set('');
  }
}
