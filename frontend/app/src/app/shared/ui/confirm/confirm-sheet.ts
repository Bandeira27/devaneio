import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { DvButton } from '../button/button';
import { SHEET_DATA, SheetRef } from '../sheet/sheet';
import { DvSheetHead } from '../sheet/sheet-head';

/** O que a folha de confirmar recebe: o título, o que vai acontecer e o texto do botão de confirmar. */
export interface ConfirmSheetData {
  title: string;
  text: string;
  action: string;
}

/**
 * Confirma uma ação que não tem volta ou mexe com muita coisa (fim do turno, revelar um fato, descartar alterações).
 * Devolve `true` ao confirmar e nada ao fechar ou voltar. O foco abre no texto, não no botão de confirmar: um Enter
 * sem querer não confirma.
 */
@Component({
  selector: 'dv-confirm-sheet',
  imports: [DvSheetHead, DvButton],
  template: `
    <dv-sheet-head [title]="data.title" />
    <p cdkFocusInitial tabindex="-1">{{ data.text }}</p>
    <div class="dv-sheet__foot">
      <button dvButton type="button" (click)="ref.close()">Voltar</button>
      <button dvButton="primary" type="button" (click)="ref.close(true)">{{ data.action }}</button>
    </div>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ConfirmSheet {
  protected readonly data = inject(SHEET_DATA) as ConfirmSheetData;
  protected readonly ref = inject<SheetRef<boolean>>(SheetRef);
}
