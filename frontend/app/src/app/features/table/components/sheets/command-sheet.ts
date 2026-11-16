import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { DvButton } from '@shared/ui/button/button';
import { DvField } from '@shared/ui/field/field';
import { DvInput } from '@shared/ui/field/input';
import { SheetRef } from '@shared/ui/sheet/sheet';
import { valueOf } from '@shared/ui/field/value-of';
import { DvSheetHead } from '@shared/ui/sheet/sheet-head';

@Component({
  selector: 'dv-command-sheet',
  imports: [DvSheetHead, DvButton, DvField, DvInput],
  template: `
    <dv-sheet-head title="Digitar um comando" />
    <form class="dv-stack" (submit)="$event.preventDefault(); send()">
      <dv-field
        label="Comando"
        hint="Por exemplo: olhar, ficha, ir floresta, testar lutar normal."
        [error]="error()"
      >
        <input
          dvInput
          type="text"
          autocomplete="off"
          autocapitalize="none"
          spellcheck="false"
          [value]="line()"
          (input)="line.set(valueOf($event))"
        />
      </dv-field>
      <button dvButton="primary" type="submit">Enviar</button>
    </form>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CommandSheet {
  protected readonly valueOf = valueOf;
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
