import { ChangeDetectionStrategy, Component, computed, input, model } from '@angular/core';
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
 * valor `''` serve de "nenhum". `value` é de duas vias; se o valor não está nas opções, ele aparece como "(não encontrado)".
 */
@Component({
  selector: 'dv-select',
  imports: [DvField, DvInput],
  templateUrl: './select.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DvSelect {
  readonly label = input.required<string>();
  readonly options = input.required<readonly SelectOption[]>();
  readonly hint = input('');
  readonly error = input('');
  readonly announce = input(true);
  readonly disabled = input(false);
  readonly value = model('');
  protected readonly fieldValue = fieldValue;
  /** As opções, e uma a mais quando o valor não está nelas: a tela não pode mostrar outra coisa que o dado. */
  protected readonly shown = computed<readonly SelectOption[]>(() => {
    const value = this.value();
    const options = this.options();
    if (options.some((o) => o.value === value)) {
      return options;
    }
    // Valor que não está nas opções: a tela mostra isso, e não outra opção (vazio é "escolha", o resto "não encontrado").
    return [
      { value, label: value === '' ? '(escolha…)' : `${value} (não encontrado)` },
      ...options,
    ];
  });
}
