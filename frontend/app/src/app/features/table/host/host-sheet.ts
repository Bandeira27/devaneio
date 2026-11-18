import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { DvNotice } from '@shared/ui/notice/notice';
import { DvSheetHead } from '@shared/ui/sheet/sheet-head';
import { TableStore } from '../table.store';
import { HostDrawer } from './host-drawer';

/**
 * A barra do anfitrião no celular: um bottom sheet com o mesmo conteúdo da barra da tela larga. O dock de ações da mesa
 * fica atrás do fundo da folha, então o resultado de uma ação (erro ou resposta) aparece aqui também.
 */
@Component({
  selector: 'dv-host-sheet',
  imports: [DvNotice, DvSheetHead, HostDrawer],
  template: `
    <dv-sheet-head title="Painel do anfitrião" />
    <div class="host-sheet">
      @if (store.actionError()) {
        <dv-notice kind="error" dismissible (dismissed)="store.dismissFeedback()">
          {{ store.actionError() }}
        </dv-notice>
      }
      @if (store.reply()) {
        <dv-notice dismissible (dismissed)="store.dismissFeedback()">
          {{ store.reply() }}
        </dv-notice>
      }
      <dv-host-drawer />
    </div>
  `,
  styles: `
    .host-sheet {
      display: grid;
      gap: var(--dv-space-4);
    }

    dv-notice {
      max-height: 10rem;
      overflow-y: auto;
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HostSheet {
  protected readonly store = inject(TableStore);
}
