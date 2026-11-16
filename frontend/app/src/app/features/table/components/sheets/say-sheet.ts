import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { DvButton } from '@shared/ui/button/button';
import { DvField } from '@shared/ui/field/field';
import { DvInput } from '@shared/ui/field/input';
import { SheetRef } from '@shared/ui/sheet/sheet';

export const MAX_SAY = 500;

@Component({
  selector: 'dv-say-sheet',
  imports: [DvButton, DvField, DvInput],
  template: `
    <div class="dv-sheet__head">
      <h2 class="dv-title">Falar com o mestre</h2>
      <button dvButton type="button" (click)="ref.close()">Fechar</button>
    </div>
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
          (input)="text.set(value($event))"
        ></textarea>
      </dv-field>
      <button dvButton="primary" type="submit">Enviar</button>
    </form>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SaySheet {
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

  protected value(event: Event): string {
    return (event.target as HTMLTextAreaElement).value;
  }
}
