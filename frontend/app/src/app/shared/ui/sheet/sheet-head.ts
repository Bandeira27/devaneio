import { ChangeDetectionStrategy, Component, inject, input } from '@angular/core';
import { DvButton } from '../button/button';
import { DvIcon } from '../icon/icon';
import { SheetRef } from './sheet';

/** Cabeçalho de uma folha: o título e o botão (só ícone, com nome acessível) que a fecha sem escolher nada. */
@Component({
  selector: 'dv-sheet-head',
  imports: [DvButton, DvIcon],
  templateUrl: './sheet-head.html',
  styleUrl: './sheet-head.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DvSheetHead {
  readonly title = input.required<string>();
  protected readonly ref = inject(SheetRef);
}
