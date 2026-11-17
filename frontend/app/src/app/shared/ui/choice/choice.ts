import { ChangeDetectionStrategy, Component, input, model } from '@angular/core';
import type { ChoiceOption } from '@shared/game/choice-option';
import { DvIcon } from '../icon/icon';

let nextId = 0;

export type { ChoiceOption };

/**
 * Escolha única entre poucas opções, em cartões grandes (alvo, arma, dificuldade, habilidade, destino). Por baixo são
 * `<input type="radio">` nativos num `<fieldset>`: setas movem a seleção, Tab entra e sai do grupo e o leitor de tela
 * anuncia o grupo e a posição. Para mais de cinco opções ainda funciona como lista. `value` é de duas vias.
 */
@Component({
  selector: 'dv-choice',
  imports: [DvIcon],
  template: `
    <fieldset>
      <legend>{{ legend() }}</legend>
      @for (option of options(); track option.value) {
        <label class="option" [class.option--selected]="option.value === value()">
          <input
            type="radio"
            [name]="name"
            [value]="option.value"
            [checked]="option.value === value()"
            (change)="value.set(option.value)"
          />
          <span class="text">
            <span class="label">{{ option.label }}</span>
            @if (option.detail) {
              <span class="detail">{{ option.detail }}</span>
            }
          </span>
          @if (option.value === value()) {
            <dv-icon name="ok" size="sm" />
          }
        </label>
      }
    </fieldset>
  `,
  styleUrl: './choice.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DvChoice {
  protected readonly name = `dv-choice-${nextId++}`;
  readonly legend = input.required<string>();
  readonly options = input.required<readonly ChoiceOption[]>();
  readonly value = model('');
}
