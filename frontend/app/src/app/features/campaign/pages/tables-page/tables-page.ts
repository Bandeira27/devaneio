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
import type { EditorTable } from '@contract/api_responses';
import { ENTRY_STEP, HOST_STEPS } from '@shared/game/entry-steps';
import { tableLine } from '@shared/game/server-tables';
import { whenOf } from '@shared/game/when';
import { DvButton } from '@shared/ui/button/button';
import { DvField } from '@shared/ui/field/field';
import { fieldValue } from '@shared/ui/field/field-value';
import { DvInput } from '@shared/ui/field/input';
import { focusElement } from '@shared/ui/focus';
import { DvNotice } from '@shared/ui/notice/notice';
import { DvSteps } from '@shared/ui/steps/steps';
import { CampaignStore } from '../../campaign.store';
import { DvIcon } from '../../../../shared/ui/icon/icon';

/**
 * As mesas de uma campanha, como o servidor as conhece quando este aparelho o enxerga (continuar, abrir, esquecer neste
 * navegador com desfazer, encerrar, ou assumir o lugar de anfitrião de uma que este navegador não conhece) e criar uma mesa nova, que pede só
 * o nome de quem vai ser o anfitrião.
 */
@Component({
  selector: 'dv-campaign-tables-page',
  imports: [DvIcon, RouterLink, DvButton, DvField, DvInput, DvNotice, DvSteps],
  providers: [CampaignStore],
  templateUrl: './tables-page.html',
  styleUrl: './tables-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TablesPage {
  /** O id da campanha, da rota `/c/:campaignId`. */
  readonly campaignId = input.required<string>();

  protected readonly fieldValue = fieldValue;
  protected readonly hostSteps = HOST_STEPS;
  protected readonly entryStep = ENTRY_STEP;
  protected readonly store = inject(CampaignStore);
  private readonly injector = inject(Injector);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  protected readonly line = (table: EditorTable): string => tableLine(table, Date.now());
  protected readonly when = (time: number): string => whenOf(time, Date.now());

  constructor() {
    effect(() => this.store.campaignId.set(this.campaignId()));
  }

  /** Esquece a mesa e leva o foco ao "Desfazer" (o botão clicado some junto com a linha). */
  protected forget(tableId: string): void {
    this.store.forget(tableId);
    this.focusLater('.tables__undo');
  }

  /** Encerra a mesa; a linha some, então o foco vai à próxima ação da lista (ou ao título, se não sobrou nenhuma). */
  protected async close(tableId: string): Promise<void> {
    if (await this.store.close(tableId)) {
      afterNextRender(
        () => {
          const root = this.host.nativeElement;
          const next = root.querySelector<HTMLElement>('.saved__link, .saved__assume');
          const heading = root.querySelector<HTMLElement>('h1');
          if (next) {
            next.focus(); // já é focável: não mexe no `tabindex`
          } else if (heading) {
            focusElement(heading);
          }
        },
        { injector: this.injector },
      );
    }
  }

  protected restore(): void {
    const id = this.store.forgotten()?.tableId;
    this.store.restore();
    this.focusLater(id ? `[data-table-id="${id}"] .saved__link` : '.saved__link');
  }

  private focusLater(selector: string): void {
    afterNextRender(() => this.host.nativeElement.querySelector<HTMLElement>(selector)?.focus(), {
      injector: this.injector,
    });
  }
}
