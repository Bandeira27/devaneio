import { computed, signal, type Signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import type { ChatMessageView, PlayerView } from '@contract/api_responses';
import { ApiClient } from '@core/api/api-client';
import { messageOf } from '@core/api/api-failure';

/**
 * O chat da mesa: as mensagens que o fluxo ao vivo trouxe, as que ainda não foram lidas e o envio de uma nova. Uma
 * mensagem de cada vez. O envio não mexe no mestre de IA nem no estado da partida (o chat é só do grupo).
 */
export class TableChat {
  readonly busy = signal(false);
  readonly error = signal('');
  /** A conversa está aberta (o cartão) ou recolhida (só a pílula com o contador). */
  readonly open = signal(false);
  /**
   * A última mensagem que a pessoa viu. `null` até a primeira carga: o histórico que já existia ao abrir a mesa não
   * conta como novidade (`baseline`).
   */
  private readonly seen = signal<number | null>(null);

  /** Mensagens dos outros que chegaram depois da última vez que a conversa foi aberta (sussurros inclusive). */
  readonly unreadMessages = computed(() => {
    const seen = this.seen();
    return seen === null
      ? []
      : this.messages().filter((message) => message.seq > seen && message.player_id !== this.you());
  });
  readonly unread = computed(() => this.unreadMessages().length);
  /** Quantas dessas são sussurros para mim. */
  readonly unreadWhispers = computed(
    () => this.unreadMessages().filter((message) => message.to === this.you()).length,
  );

  /** Quem pode receber um sussurro: os outros jogadores da mesa (o anfitrião é um deles). */
  readonly recipients = computed(() => this.players().filter((player) => player.id !== this.you()));
  private readonly chosen = signal('');
  /** Para quem vai a próxima mensagem: o id de um jogador (sussurro) ou `''` para a mesa toda. */
  readonly recipient = computed(() => {
    const id = this.chosen();
    return this.recipients().some((player) => player.id === id) ? id : '';
  });
  /** O sussurro escolhido já não tem para quem ir (o jogador deixou a mesa): nunca vira mensagem pública sozinho. */
  readonly recipientGone = computed(() => this.chosen() !== '' && this.recipient() === '');
  /** O nome de quem recebe o sussurro em preparo, ou `''` quando a mensagem vai para a mesa toda. */
  readonly recipientName = computed(
    () => this.recipients().find((player) => player.id === this.recipient())?.name ?? '',
  );

  constructor(
    private readonly api: ApiClient,
    private readonly tableId: () => string,
    readonly messages: Signal<ChatMessageView[]>,
    private readonly you: Signal<string>,
    /** Entrega a mensagem enviada ao fluxo ao vivo, para aparecer já, sem esperar a próxima volta do long-poll. */
    private readonly deliver: (message: ChatMessageView) => void,
    private readonly players: Signal<PlayerView[]>,
  ) {}

  /** Escolhe para quem vai a próxima mensagem (`''` = a mesa toda). */
  sendTo(playerId: string): void {
    this.chosen.set(playerId);
  }

  toggle(): void {
    this.open.update((open) => !open);
  }

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
    if (this.recipientGone()) {
      this.error.set('Quem ia receber o sussurro saiu da mesa: escolha para quem enviar.');
      return false;
    }
    this.busy.set(true);
    this.error.set('');
    try {
      this.deliver(
        await firstValueFrom(
          this.api.postChat(this.tableId(), { text, to: this.recipient() || null }),
        ),
      );
      return true;
    } catch (error) {
      this.error.set(messageOf(error));
      return false;
    } finally {
      this.busy.set(false);
    }
  }
}
