import {
  ChangeDetectionStrategy,
  Component,
  effect,
  input,
  model,
  signal,
  untracked,
} from '@angular/core';
import { fromLines, toLines } from '@shared/game/campaign-edit';
import { DvField } from '@shared/ui/field/field';
import { fieldValue } from '@shared/ui/field/field-value';
import { DvInput } from '@shared/ui/field/input';

/**
 * Uma lista de textos curtos escrita numa caixa, uma por linha (notas privadas, metas). O texto da caixa é do
 * componente: a lista de fora só o troca quando muda por outro motivo, para a linha em branco que o autor acabou de
 * abrir com Enter não sumir enquanto ele digita.
 */
@Component({
  selector: 'dv-lines-field',
  imports: [DvField, DvInput],
  template: `
    <dv-field [label]="label()" [hint]="hint()" [error]="error()" [announce]="false">
      <textarea dvInput rows="3" [value]="text()" (input)="typed($event)"></textarea>
    </dv-field>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LinesField {
  readonly label = input.required<string>();
  readonly hint = input('Uma por linha.');
  readonly error = input('');
  readonly lines = model<readonly string[]>([]);
  protected readonly text = signal('');

  constructor() {
    effect(() => {
      const lines = this.lines();
      // Só `lines` dispara: o texto da caixa é lido sem ser dependência (senão cada tecla reexecutaria o efeito).
      const current = untracked(() => this.text());
      if (JSON.stringify(toLines(current)) !== JSON.stringify(lines)) {
        this.text.set(fromLines(lines));
      }
    });
  }

  protected typed(event: Event): void {
    const text = fieldValue(event);
    this.text.set(text);
    this.lines.set(toLines(text));
  }
}
