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
  templateUrl: './host-sheet.html',
  styleUrl: './host-sheet.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HostSheet {
  protected readonly store = inject(TableStore);
}
