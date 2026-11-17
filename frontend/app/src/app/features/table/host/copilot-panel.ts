import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { ApiClient } from '@core/api/api-client';
import { DvBadge } from '@shared/ui/badge/badge';
import { DvButton } from '@shared/ui/button/button';
import { DvField } from '@shared/ui/field/field';
import { fieldValue } from '@shared/ui/field/field-value';
import { DvInput } from '@shared/ui/field/input';
import { DvNotice } from '@shared/ui/notice/notice';
import { DvState } from '@shared/ui/state/state';
import { MAX_SAY } from '../components/sheets/say-sheet';
import { TableStore } from '../table.store';
import { CopilotActions } from './copilot.actions';

/**
 * O copiloto do anfitrião: uma pergunta de cada vez, sem memória, e a resposta só para ele (nunca vai ao feed nem ao
 * grupo). A resposta e as notas são texto puro. Sem mestre de IA na mesa, a seção diz que o copiloto não está disponível.
 * O leitor de tela ouve a resposta quando ela chega (`role="status"`).
 */
@Component({
  selector: 'dv-copilot-panel',
  imports: [DvBadge, DvButton, DvField, DvInput, DvNotice, DvState],
  templateUrl: './copilot-panel.html',
  styleUrl: './copilot-panel.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CopilotPanel {
  protected readonly store = inject(TableStore);
  protected readonly copilot = new CopilotActions(inject(ApiClient), () => this.store.tableId());
  protected readonly fieldValue = fieldValue;
  protected readonly max = MAX_SAY;
  protected readonly text = signal('');
  protected readonly hint = signal('');

  protected async send(): Promise<void> {
    const text = this.text().trim();
    if (text === '') {
      this.hint.set('Escreva a pergunta.');
      return;
    }
    this.hint.set('');
    if (await this.copilot.ask(text)) {
      this.text.set('');
    }
  }
}
