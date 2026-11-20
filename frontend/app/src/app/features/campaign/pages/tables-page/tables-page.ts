import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Injector,
  afterNextRender,
  effect,
  inject,
  input,
} from '@angular/core';
import { RouterLink } from '@angular/router';
import type { ArchivedTable, EditorTable } from '@contract/api_responses';
import {
  archivedDetails,
  archivedLine,
  tableDetails,
  tableLine,
  tableName,
} from '@shared/game/server-tables';
import { whenOf } from '@shared/game/when';
import { DvButton } from '@shared/ui/button/button';
import { focusElement } from '@shared/ui/focus';
import { DvNotice } from '@shared/ui/notice/notice';
import { CampaignStore } from '../../campaign.store';
import { DvIcon } from '../../../../shared/ui/icon/icon';

/**
 * As mesas de uma campanha, como o servidor as conhece quando este aparelho o enxerga (continuar, abrir, esquecer neste
 * navegador com desfazer, arquivar, ou assumir o lugar de anfitrião de uma que este navegador não conhece) e levar a criar uma mesa nova (a tela
 * própria, `NewTablePage`).
 */
@Component({
  selector: 'dv-campaign-tables-page',
  imports: [DvIcon, RouterLink, DvButton, DvNotice],
  providers: [CampaignStore],
  templateUrl: './tables-page.html',
  styleUrl: './tables-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TablesPage {
  /** O id da campanha, da rota `/c/:campaignId`. */
  readonly campaignId = input.required<string>();

  protected readonly store = inject(CampaignStore);
  private readonly injector = inject(Injector);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  protected readonly line = (table: EditorTable): string => tableLine(table, Date.now());
  protected readonly archivedLine = (table: ArchivedTable): string =>
    archivedLine(table, Date.now());
  protected readonly name = tableName;
  protected readonly details = (table: EditorTable): string => tableDetails(table, Date.now());
  protected readonly archivedDetails = (table: ArchivedTable): string =>
    archivedDetails(table, Date.now());
  protected readonly when = (time: number): string => whenOf(time, Date.now());

  constructor() {
    effect(() => this.store.campaignId.set(this.campaignId()));
  }

  /** Esquece a mesa e leva o foco ao "Desfazer" (o botão clicado some junto com a linha). */
  protected forget(tableId: string): void {
    this.store.forget(tableId);
    this.focusLater('.tables__undo');
  }

  /** Arquiva a mesa; a linha vai para “Mesas arquivadas”, então o foco vai à ação dela lá (ou ao título). */
  protected async archive(tableId: string): Promise<void> {
    if (await this.store.archive(tableId)) {
      this.focusLater(`[data-table-id="${tableId}"] .saved__history`, 'h1');
    }
  }

  /** Restaura uma mesa arquivada; ela reaparece na lista de cima, então o foco vai à ação dela (ou ao título). */
  protected async restoreArchived(tableId: string): Promise<void> {
    if (await this.store.restoreArchived(tableId)) {
      this.focusLater(
        `[data-table-id="${tableId}"] .saved__link, [data-table-id="${tableId}"] .saved__assume`,
        'h1',
      );
    }
  }

  /** Apaga de vez uma mesa arquivada (depois de confirmar); o foco vai à próxima arquivada, ou ao título. */
  protected async purge(table: ArchivedTable): Promise<void> {
    if (await this.store.purge(table)) {
      this.focusLater('.saved__history', 'h1');
    }
  }

  protected restore(): void {
    const id = this.store.forgotten()?.tableId;
    this.store.restore();
    this.focusLater(id ? `[data-table-id="${id}"] .saved__link` : '.saved__link');
  }

  /** Depois de renderizar, foca o primeiro elemento de `selector`; sem ele, o `fallback` (um título leva `tabindex`). */
  private focusLater(selector: string, fallback?: string): void {
    afterNextRender(
      () => {
        const root = this.host.nativeElement;
        const target = root.querySelector<HTMLElement>(selector);
        if (target) {
          target.focus();
        } else if (fallback) {
          const heading = root.querySelector<HTMLElement>(fallback);
          if (heading) {
            focusElement(heading);
          }
        }
      },
      { injector: this.injector },
    );
  }
}
