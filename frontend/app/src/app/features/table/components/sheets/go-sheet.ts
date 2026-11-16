import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { go } from '@shared/game/commands';
import { SHEET_DATA, SheetRef } from '@shared/ui/sheet/sheet';
import { DvButton } from '@shared/ui/button/button';
import { DvSheetHead } from '@shared/ui/sheet/sheet-head';

/** O que a folha de ir recebe: as saídas do local. */
export interface GoSheetData {
  exits: { id: string; name: string }[];
}

/** Folha de ir para outro local; devolve a linha de comando. */
@Component({
  selector: 'dv-go-sheet',
  imports: [DvSheetHead, DvButton],
  template: `
    <dv-sheet-head title="Ir para" />
    @if (data.exits.length === 0) {
      <p class="dv-note">Não há saídas daqui.</p>
    }
    <div class="dv-stack">
      @for (exit of data.exits; track exit.id) {
        <button
          dvButton
          type="button"
          [attr.cdkFocusInitial]="$first ? '' : null"
          (click)="ref.close(command(exit.id))"
        >
          {{ exit.name }}
        </button>
      }
    </div>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GoSheet {
  protected readonly data = inject(SHEET_DATA) as GoSheetData;
  protected readonly ref = inject<SheetRef<string>>(SheetRef);

  protected command(id: string): string {
    return go(id);
  }
}
