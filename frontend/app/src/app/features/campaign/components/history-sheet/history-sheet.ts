import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import type { LogEvent } from '@contract/api_responses';
import { messageOf } from '@core/api/api-failure';
import { ServerTables } from '@core/tables/server-tables';
import { DvButton } from '@shared/ui/button/button';
import { DvIcon } from '@shared/ui/icon/icon';
import { SHEET_DATA, SheetRef } from '@shared/ui/sheet/sheet';
import { DvSheetHead } from '@shared/ui/sheet/sheet-head';
import { DvSheetFoot } from '@shared/ui/sheet/sheet-foot';
import { DvState } from '@shared/ui/state/state';

/** O que a folha do histórico recebe: a mesa arquivada e o nome dela para o título. */
export interface HistorySheetData {
  tableId: string;
  title: string;
}

/**
 * O histórico de uma mesa arquivada: o log inteiro, na ordem, em texto. Só leitura; fecha no botão ou no voltar. A
 * mesa arquivada não está no jogo, então a folha pergunta ao servidor (editor) em vez de abrir a mesa.
 */
@Component({
  selector: 'dv-history-sheet',
  imports: [DvButton, DvIcon, DvSheetHead, DvSheetFoot, DvState],
  templateUrl: './history-sheet.html',
  styleUrl: './history-sheet.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HistorySheet implements OnInit {
  protected readonly data = inject(SHEET_DATA) as HistorySheetData;
  protected readonly ref = inject<SheetRef<boolean>>(SheetRef);
  private readonly serverTables = inject(ServerTables);

  protected readonly state = signal<'loading' | 'ready' | 'failed'>('loading');
  protected readonly error = signal('');
  /** Tentando de novo depois de uma falha: o botão fica na tela (com o foco) e só mostra o envio. */
  protected readonly retrying = signal(false);
  protected readonly events = signal<LogEvent[]>([]);

  ngOnInit(): void {
    void this.load();
  }

  protected async load(): Promise<void> {
    if (this.state() === 'failed') {
      this.retrying.set(true); // não troca de tela: o botão que tinha o foco continua lá
    } else {
      this.state.set('loading');
    }
    try {
      const log = await this.serverTables.history(this.data.tableId);
      this.events.set(log.events.filter((event) => event.text !== ''));
      this.state.set('ready');
    } catch (error) {
      this.error.set(messageOf(error));
      this.state.set('failed');
    } finally {
      this.retrying.set(false);
    }
  }
}
