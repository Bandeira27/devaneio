import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Injector,
  afterNextRender,
  effect,
  inject,
  input,
  signal,
  viewChild,
} from '@angular/core';
import type { ChatMessageView } from '@contract/api_responses';
import { DvBadge } from '@shared/ui/badge/badge';
import { DvButton } from '@shared/ui/button/button';
import { fieldValue } from '@shared/ui/field/field-value';
import { DvIcon } from '@shared/ui/icon/icon';
import { TableStore } from '../../table.store';

/** O limite do texto de uma mensagem, o mesmo do servidor (`MAX_CHAT` em `server/models/requests.py`). */
const MAX_CHAT_TEXT = 500;

/**
 * A conversa da mesa, flutuante e **não modal**: recolhida é uma pílula com o contador de mensagens novas; aberta é um
 * cartão que não escurece nem prende o foco, para a história e as ações seguirem à vista. No celular fica acima da
 * barra de ações; na tela larga, no canto inferior direito (e à esquerda da barra do anfitrião, quando ela está
 * aberta). Só do grupo: o mestre de IA não lê nada daqui. Mesa encerrada é só leitura.
 *
 * Acessibilidade: o cartão é uma região com nome; Esc o recolhe e devolve o foco à pílula; a lista é um `log` educado;
 * quem chega com a conversa recolhida é anunciado sem roubar o foco.
 */
@Component({
  selector: 'dv-chat-dock',
  imports: [DvBadge, DvButton, DvIcon],
  templateUrl: './chat-dock.html',
  styleUrl: './chat-dock.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '[class.chat--aside]': 'asideOpen()' },
})
export class ChatDock {
  /** A barra do anfitrião está aberta e encaixada à direita: o cartão cede o canto. */
  readonly asideOpen = input(false);

  protected readonly store = inject(TableStore);
  protected readonly chat = this.store.chat;
  protected readonly max = MAX_CHAT_TEXT;
  protected readonly text = signal('');
  protected readonly fieldValue = fieldValue;
  protected readonly you = () => this.store.table()?.you ?? '';
  private readonly log = viewChild<ElementRef<HTMLElement>>('log');
  private readonly field = viewChild<ElementRef<HTMLInputElement>>('field');
  private readonly pill = viewChild<ElementRef<HTMLButtonElement>>('pill');
  private readonly card = viewChild<ElementRef<HTMLElement>>('card');
  private readonly injector = inject(Injector);

  constructor() {
    effect(() => {
      // Aberta, a conversa conta como lida e a lista acompanha a última mensagem.
      if (!this.chat.open()) {
        return;
      }
      this.chat.messages();
      this.chat.markRead();
      afterNextRender(
        () => {
          const log = this.log()?.nativeElement;
          if (log) {
            log.scrollTop = log.scrollHeight;
          }
        },
        { injector: this.injector },
      );
    });
  }

  protected unreadLabel(): string {
    const unread = this.chat.unread();
    const whispers = this.chat.unreadWhispers();
    const base = unread === 1 ? '1 mensagem nova' : `${unread} mensagens novas`;
    if (whispers === 0) {
      return base;
    }
    return `${base}, ${whispers === 1 ? '1 sussurro' : `${whispers} sussurros`} para você`;
  }

  /** Dá para responder em sussurro a quem ainda está na mesa. */
  protected canReplyTo(playerId: string): boolean {
    return this.chat.recipients().some((player) => player.id === playerId);
  }

  /** O selo de um sussurro: "para você" ou "para fulano" (quem sussurrou já está no nome da mensagem). */
  protected whisperLabel(message: ChatMessageView): string {
    return message.to === this.you()
      ? 'sussurro para você'
      : `sussurro para ${message.to_name ?? 'alguém'}`;
  }

  /** Responder a um sussurro: a próxima mensagem vai só para quem o enviou, com o foco no campo. */
  protected reply(playerId: string): void {
    this.chat.sendTo(playerId);
    afterNextRender(() => this.field()?.nativeElement.focus(), { injector: this.injector });
  }

  /** Abre ou recolhe; ao abrir o foco vai ao campo, ao recolher volta à pílula. */
  protected toggle(): void {
    this.chat.toggle();
    this.chat.error.set('');
    afterNextRender(
      () => {
        // Mesa encerrada não tem campo: o foco vai ao próprio cartão, para o Esc seguir valendo.
        const target = this.chat.open() ? (this.field() ?? this.card()) : this.pill();
        target?.nativeElement.focus();
      },
      { injector: this.injector },
    );
  }

  protected async send(): Promise<void> {
    const text = this.text().trim();
    if (text === '' || (await this.chat.send(text)) === false) {
      return;
    }
    this.text.set('');
  }

  protected iso(at: number): string {
    return new Date(at * 1000).toISOString();
  }

  protected clock(at: number): string {
    return new Date(at * 1000).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
  }
}
