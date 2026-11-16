import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { DvButton } from '@shared/ui/button/button';
import { DvField } from '@shared/ui/field/field';
import { DvInput } from '@shared/ui/field/input';
import { SheetRef } from '@shared/ui/sheet/sheet';
import { fieldValue } from '@shared/ui/field/field-value';
import { DvSheetHead } from '@shared/ui/sheet/sheet-head';

export const MAX_SAY = 500;

@Component({
  selector: 'dv-say-sheet',
  imports: [DvSheetHead, DvButton, DvField, DvInput],
  template: `
    <dv-sheet-head title="Falar com o mestre" />
    <form class="dv-stack" (submit)="$event.preventDefault(); send()">
      <dv-field
        label="O que você diz ou faz"
        hint="O mestre responde e, se for o caso, resolve a ação por você."
        [error]="error()"
      >
        <textarea
          dvInput
          rows="3"
          [attr.maxlength]="max"
          [value]="text()"
          (input)="text.set(fieldValue($event))"
        ></textarea>
      </dv-field>
      <button dvButton="primary" type="submit">Enviar</button>
    </form>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SaySheet {
  protected readonly fieldValue = fieldValue;
  protected readonly ref = inject<SheetRef<string>>(SheetRef);
  protected readonly max = MAX_SAY;
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
