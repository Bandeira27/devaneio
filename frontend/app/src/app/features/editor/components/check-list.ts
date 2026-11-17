import { ChangeDetectionStrategy, Component, input, model } from '@angular/core';
import type { SelectOption } from '@shared/ui/select/select';

/**
 * Uma lista de caixas de marcar (as ligações de um local, os requisitos de um marco): cada opção é uma caixa nativa
 * com o rótulo ao lado, num `fieldset` com legenda. `selected` é de duas vias; marcar ou desmarcar mantém a ordem das
 * opções que já estavam marcadas.
 */
@Component({
  selector: 'dv-check-list',
  template: `
    <fieldset class="checks">
      <legend>{{ legend() }}</legend>
      @if (hint()) {
        <p class="dv-note">{{ hint() }}</p>
      }
      @for (option of options(); track option.value) {
        <label class="check">
          <input
            type="checkbox"
            [checked]="selected().includes(option.value)"
            (change)="toggle(option.value, $event)"
          />
          {{ option.label }}
        </label>
      }
    </fieldset>
  `,
  styleUrl: './check-list.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CheckList {
  readonly legend = input.required<string>();
  readonly hint = input('');
  readonly options = input.required<readonly SelectOption[]>();
  readonly selected = model.required<readonly string[]>();

  protected toggle(value: string, event: Event): void {
    const on = (event.target as HTMLInputElement).checked;
    this.selected.update((list) => (on ? [...list, value] : list.filter((v) => v !== value)));
  }
}
