import { ChangeDetectionStrategy, Component, input, model } from '@angular/core';
import { DvField } from '../field/field';
import { fieldValue } from '../field/field-value';
import { DvInput } from '../field/input';

/** Uma opção de um `dv-select`: o valor que volta e o texto que se lê. */
export interface SelectOption {
  value: string;
  label: string;
}

/**
 * Escolha de um valor numa lista, com rótulo, dica e erro (o `<select>` nativo dentro de um `dv-field`: teclado e
 * leitor de tela vêm do navegador). Serve para apontar para outro item (local, NPC, facção, sistema). Uma opção de
 * valor `''` serve de "nenhum". `value` é de duas vias; se o valor não está nas opções, o navegador mostra a primeira.
 */
@Component({
  selector: 'dv-select',
  imports: [DvField, DvInput],
  template: `
    <dv-field [label]="label()" [hint]="hint()" [error]="error()">
      <select dvInput [disabled]="disabled()" (change)="value.set(fieldValue($event))">
        @for (option of options(); track option.value) {
          <option [value]="option.value" [selected]="option.value === value()">
            {{ option.label }}
          </option>
        }
      </select>
    </dv-field>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DvSelect {
  readonly label = input.required<string>();
  readonly options = input.required<readonly SelectOption[]>();
  readonly hint = input('');
  readonly error = input('');
  readonly disabled = input(false);
  readonly value = model('');
  protected readonly fieldValue = fieldValue;
}
