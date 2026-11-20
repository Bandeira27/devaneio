import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  afterNextRender,
  effect,
  inject,
  signal,
  viewChild,
  Injector,
} from '@angular/core';
import { DvBadge } from '@shared/ui/badge/badge';
import { DvButton } from '@shared/ui/button/button';
import { DvField } from '@shared/ui/field/field';
import { fieldValue } from '@shared/ui/field/field-value';
import { DvInput } from '@shared/ui/field/input';
import { DvNotice } from '@shared/ui/notice/notice';
import { DvSheetFoot } from '@shared/ui/sheet/sheet-foot';
import { DvSheetHead } from '@shared/ui/sheet/sheet-head';
import { TableStore } from '../../table.store';

/** O limite do texto de uma mensagem, o mesmo do servidor (`MAX_CHAT_TEXT`). */
const MAX_CHAT_TEXT = 500;

/**
 * A conversa da mesa: as mensagens do grupo e o campo para escrever. Só do grupo: o mestre de IA não lê nada daqui.
 * Abre com o store da mesa (`injector` de quem abriu) e fica atualizada pelo fluxo ao vivo enquanto está aberta.
 * Mesa encerrada é só leitura.
 */
@Component({
  selector: 'dv-chat-sheet',
  imports: [DvBadge, DvButton, DvField, DvInput, DvNotice, DvSheetFoot, DvSheetHead],
  template: `
    <dv-sheet-head title="Conversa" />
    <ol #log class="chat" role="log" aria-label="Mensagens da conversa" tabindex="0">
      @for (message of chat.messages(); track message.seq) {
        <li class="chat__message" [class.chat__message--mine]="message.player_id === you()">
          <span class="chat__who">
            <span class="chat__name">{{ message.name }}</span>
            @if (message.role === 'host') {
              <dv-badge tone="info">anfitrião</dv-badge>
            }
            <time class="dv-note" [attr.datetime]="iso(message.at)">{{ clock(message.at) }}</time>
          </span>
          <span class="chat__text">{{ message.text }}</span>
        </li>
      } @empty {
        <li class="dv-note">
          Ninguém falou ainda. Esta conversa é só do grupo: o mestre de IA não a lê.
        </li>
      }
    </ol>
    @if (!store.canChat()) {
      <dv-notice>A partida foi encerrada: a conversa fica só para ler.</dv-notice>
    } @else {
      <form class="dv-stack" (submit)="$event.preventDefault(); send()">
        <dv-field label="Mensagem para o grupo" [error]="chat.error()">
          <input
            dvInput
            cdkFocusInitial
            type="text"
            autocomplete="off"
            enterkeyhint="send"
            [attr.maxlength]="max"
            [value]="text()"
            (input)="text.set(fieldValue($event))"
          />
        </dv-field>
        <dv-sheet-foot>
          <span class="dv-note" aria-hidden="true">{{ text().length }}/{{ max }}</span>
          <button dvButton="primary" type="submit" [dvLoading]="chat.busy()">Enviar</button>
        </dv-sheet-foot>
      </form>
    }
  `,
  styles: `
    .chat {
      display: grid;
      gap: var(--dv-space-3);
      max-height: 24rem;
      margin: 0 0 var(--dv-space-4);
      padding: 0;
      overflow-y: auto;
      list-style: none;
    }

    .chat__message {
      display: grid;
      gap: var(--dv-space-1);
    }

    .chat__who {
      display: flex;
      flex-wrap: wrap;
      align-items: baseline;
      gap: var(--dv-space-1) var(--dv-space-2);
    }

    /* O nome é texto livre do jogador: quebra em vez de estourar, e a minha mensagem tem a borda da cor da tinta. */
    .chat__name {
      min-width: 0;
      overflow-wrap: anywhere;
      font-family: var(--dv-font-narration);
    }

    .chat__text {
      overflow-wrap: anywhere;
    }

    .chat__message--mine {
      padding-inline-start: var(--dv-space-3);
      border-inline-start: var(--dv-border-width-strong) solid var(--dv-ink);
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ChatSheet {
  protected readonly store = inject(TableStore);
  protected readonly chat = this.store.chat;
  protected readonly max = MAX_CHAT_TEXT;
  protected readonly text = signal('');
  protected readonly fieldValue = fieldValue;
  protected readonly you = () => this.store.table()?.you ?? '';
  private readonly log = viewChild<ElementRef<HTMLElement>>('log');
  private readonly injector = inject(Injector);

  constructor() {
    this.chat.error.set(''); // um erro de uma abertura anterior não reaparece
    effect(() => {
      // Aberta, a conversa conta como lida; e a lista acompanha a última mensagem.
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
