import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { go } from '@shared/game/commands';
import { SHEET_DATA, SheetRef } from '@shared/ui/sheet/sheet';
import { DvButton } from '@shared/ui/button/button';

export interface GoSheetData {
  exits: { id: string; name: string }[];
}

@Component({
  selector: 'dv-go-sheet',
  imports: [DvButton],
  template: `
    <div class="dv-sheet__head">
      <h2 class="dv-title">Ir para</h2>
      <button dvButton type="button" (click)="ref.close()">Fechar</button>
    </div>
    @if (data.exits.length === 0) {
      <p class="dv-note">Não há saídas daqui.</p>
    }
    <div class="dv-stack">
      @for (exit of data.exits; track exit.id) {
        <button dvButton type="button" (click)="ref.close(command(exit.id))">
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
