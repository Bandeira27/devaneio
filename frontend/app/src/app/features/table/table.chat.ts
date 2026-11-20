import { computed, signal, type Signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import type { ChatMessageView } from '@contract/api_responses';
import { ApiClient } from '@core/api/api-client';
import { messageOf } from '@core/api/api-failure';

/**
 * O chat da mesa: as mensagens que o fluxo ao vivo trouxe, as que ainda não foram lidas e o envio de uma nova. Uma
 * mensagem de cada vez. O envio não mexe no mestre de IA nem no estado da partida (o chat é só do grupo).
 */
export class TableChat {
  readonly busy = signal(false);
  readonly error = signal('');
  /**
   * A última mensagem que a pessoa viu. `null` até a primeira carga: o histórico que já existia ao abrir a mesa não
   * conta como novidade (`baseline`).
   */
  private readonly seen = signal<number | null>(null);

  /** Mensagens dos outros que chegaram depois da última vez que a conversa foi aberta. */
  readonly unread = computed(() => {
    const seen = this.seen();
    return seen === null
      ? 0
      : this.messages().filter((message) => message.seq > seen && message.player_id !== this.you())
          .length;
  });

  constructor(
    private readonly api: ApiClient,
    private readonly tableId: () => string,
    readonly messages: Signal<ChatMessageView[]>,
    private readonly you: Signal<string>,
    /** Entrega a mensagem enviada ao fluxo ao vivo, para aparecer já, sem esperar a próxima volta do long-poll. */
    private readonly deliver: (message: ChatMessageView) => void,
  ) {}

  /** Marca o que já existe como visto, uma vez só: o histórico da abertura da mesa não conta como novidade. */
  baseline(): void {
    if (this.seen() === null) {
      this.markRead();
    }
  }

  /** Marca tudo o que já chegou como lido. */
  markRead(): void {
    const all = this.messages();
    this.seen.set(all.at(-1)?.seq ?? 0);
  }

  /** Manda uma mensagem à mesa; devolve se o servidor a aceitou. */
  async send(text: string): Promise<boolean> {
    if (this.busy()) {
      return false;
    }
    this.busy.set(true);
    this.error.set('');
    try {
      this.deliver(await firstValueFrom(this.api.postChat(this.tableId(), { text })));
      return true;
    } catch (error) {
      this.error.set(messageOf(error));
      return false;
    } finally {
      this.busy.set(false);
    }
  }
}
