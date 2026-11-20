import { booleanAttribute, ChangeDetectionStrategy, Component, input, model } from '@angular/core';
import type { ChoiceOption } from '@shared/game/choice-option';
import { DvIcon } from '../icon/icon';

let nextId = 0;

export type { ChoiceOption };

/**
 * Escolha única entre poucas opções, em cartões grandes (alvo, arma, dificuldade, habilidade, destino). Por baixo são
 * `<input type="radio">` nativos num `<fieldset [class.fieldset--grid]="grid()">`: setas movem a seleção, Tab entra e sai do grupo e o leitor de tela
 * anuncia o grupo e a posição. Para mais de cinco opções ainda funciona como lista. `value` é de duas vias.
 */
@Component({
  selector: 'dv-choice',
  imports: [DvIcon],
  templateUrl: './choice.html',
  styleUrl: './choice.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DvChoice {
  protected readonly name = `dv-choice-${nextId++}`;
  readonly legend = input.required<string>();
  readonly options = input.required<readonly ChoiceOption[]>();
  readonly value = model('');
  /** Muitas opções curtas (as habilidades de um teste): em duas colunas, para a lista não passar da altura da folha. */
  readonly grid = input(false, { transform: booleanAttribute });
}
