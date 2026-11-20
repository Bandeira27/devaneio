import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { MAX_LINE } from '@shared/game/commands';
import { DvButton } from '@shared/ui/button/button';
import { DvField } from '@shared/ui/field/field';
import { DvInput } from '@shared/ui/field/input';
import { SheetRef } from '@shared/ui/sheet/sheet';
import { fieldValue } from '@shared/ui/field/field-value';
import { DvSheetHead } from '@shared/ui/sheet/sheet-head';
import { DvSheetFoot } from '@shared/ui/sheet/sheet-foot';

/** Folha de falar com o mestre de IA; devolve o texto escrito. */
@Component({
  selector: 'dv-say-sheet',
  imports: [DvSheetHead, DvSheetFoot, DvButton, DvField, DvInput],
  templateUrl: './say-sheet.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SaySheet {
  protected readonly fieldValue = fieldValue;
  protected readonly ref = inject<SheetRef<string>>(SheetRef);
  protected readonly max = MAX_LINE;
  protected readonly text = signal('');
  protected readonly error = signal('');

  protected send(): void {
    const text = this.text().trim();
    if (text === '') {
      this.error.set('Escreva o que você quer dizer ou fazer.');
      return;
    }
    this.ref.close(text);
  }
}
