import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { DvButton } from '@shared/ui/button/button';
import { DvField } from '@shared/ui/field/field';
import { DvInput } from '@shared/ui/field/input';
import { SheetRef } from '@shared/ui/sheet/sheet';
import { fieldValue } from '@shared/ui/field/field-value';
import { DvSheetHead } from '@shared/ui/sheet/sheet-head';
import { DvSheetFoot } from '@shared/ui/sheet/sheet-foot';

/** Folha de digitar um comando; devolve a linha escrita. */
@Component({
  selector: 'dv-command-sheet',
  imports: [DvSheetHead, DvSheetFoot, DvButton, DvField, DvInput],
  templateUrl: './command-sheet.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CommandSheet {
  protected readonly fieldValue = fieldValue;
  protected readonly ref = inject<SheetRef<string>>(SheetRef);
  protected readonly line = signal('');
  protected readonly error = signal('');

  protected send(): void {
    const line = this.line().trim();
    if (line === '') {
      this.error.set('Escreva um comando.');
      return;
    }
    this.ref.close(line);
  }
}
