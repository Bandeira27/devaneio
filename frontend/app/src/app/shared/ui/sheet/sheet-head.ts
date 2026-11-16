import { ChangeDetectionStrategy, Component, inject, input } from '@angular/core';
import { DvButton } from '../button/button';
import { SheetRef } from './sheet';

/** Cabeçalho de uma folha: o título e o botão que a fecha, sem escolher nada. */
@Component({
  selector: 'dv-sheet-head',
  imports: [DvButton],
  template: `
    <div class="dv-sheet__head">
      <h2 class="dv-title">{{ title() }}</h2>
      <button dvButton type="button" (click)="ref.close()">Fechar</button>
    </div>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DvSheetHead {
  readonly title = input.required<string>();
  protected readonly ref = inject(SheetRef);
}
