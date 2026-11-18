import { ChangeDetectionStrategy, Component, inject, input } from '@angular/core';
import { DvButton } from '../button/button';
import { DvIcon } from '../icon/icon';
import { SheetRef } from './sheet';

/** Cabeçalho de uma folha: o título e o botão (só ícone, com nome acessível) que a fecha sem escolher nada. */
@Component({
  selector: 'dv-sheet-head',
  imports: [DvButton, DvIcon],
  template: `
    <div class="dv-sheet__head">
      <h2 class="dv-section">{{ title() }}</h2>
      <button
        dvButton
        class="dv-sheet__close"
        type="button"
        aria-label="Fechar"
        (click)="ref.close()"
      >
        <dv-icon name="close" />
      </button>
    </div>
  `,
  styles: ':host { display: block; }',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DvSheetHead {
  readonly title = input.required<string>();
  protected readonly ref = inject(SheetRef);
}
