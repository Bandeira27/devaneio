import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Injector,
  afterNextRender,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { MAX_LINE } from '@shared/game/commands';
import { DvBadge } from '@shared/ui/badge/badge';
import { DvButton } from '@shared/ui/button/button';
import { DvField } from '@shared/ui/field/field';
import { fieldValue } from '@shared/ui/field/field-value';
import { DvInput } from '@shared/ui/field/input';
import { DvNotice } from '@shared/ui/notice/notice';
import { focusElement } from '@shared/ui/focus';
import { TableStore } from '../table.store';
import { HostSession } from './host-session';
import { DvIcon } from '../../../shared/ui/icon/icon';

/**
 * O copiloto do anfitrião: uma pergunta de cada vez, sem memória, e a resposta só para ele (nunca vai ao feed nem ao
 * grupo). A resposta e as notas são texto puro. Sem mestre de IA na mesa, a seção diz que o copiloto não está disponível.
 * O leitor de tela ouve a resposta quando ela chega (`role="status"`).
 */
@Component({
  selector: 'dv-copilot-panel',
  imports: [DvIcon, DvBadge, DvButton, DvField, DvInput, DvNotice],
  templateUrl: './copilot-panel.html',
  styleUrl: './copilot-panel.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CopilotPanel {
  protected readonly store = inject(TableStore);
  protected readonly copilot = inject(HostSession).copilot;
  protected readonly fieldValue = fieldValue;
  protected readonly max = MAX_LINE;
  protected readonly text = signal('');
  protected readonly hint = signal('');
  private readonly injector = inject(Injector);
  private readonly question = viewChild<ElementRef<HTMLElement>>('question');
  private readonly reply = viewChild<ElementRef<HTMLElement>>('reply');

  protected async send(): Promise<void> {
    // O servidor recusa quebra de linha (a pergunta é uma linha só): o que foi colado em várias linhas vira espaço.
    const text = this.text().replace(/\s+/g, ' ').trim();
    if (text === '') {
      this.hint.set('Escreva a pergunta.');
      return;
    }
    this.hint.set('');
    if (await this.copilot.ask(text)) {
      this.text.set('');
      // A resposta pode ser longa: o foco vai a ela (o leitor de tela a lê uma vez), e o aviso vivo diz só que chegou.
      this.focusAfterRender(this.reply);
    }
  }

  /** Limpa a resposta; o botão some, então o foco volta à pergunta. */
  protected clear(): void {
    this.copilot.clear();
    this.focusAfterRender(this.question);
  }

  private focusAfterRender(target: () => ElementRef<HTMLElement> | undefined): void {
    afterNextRender(
      () => {
        const el = target()?.nativeElement;
        if (el) {
          focusElement(el);
        }
      },
      { injector: this.injector },
    );
  }
}
