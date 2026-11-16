import { ChangeDetectionStrategy, Component, computed, input, model } from '@angular/core';
import { DvButton } from '../button/button';

let nextId = 0;

/** Valor inteiro com − e + dentro de um mínimo e um máximo (os atributos do personagem). */
@Component({
  selector: 'dv-stepper',
  imports: [DvButton],
  templateUrl: './stepper.html',
  styleUrl: './stepper.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DvStepper {
  protected readonly labelId = `dv-stepper-${nextId++}`;
  readonly label = input.required<string>();
  readonly min = input.required<number>();
  readonly max = input.required<number>();
  readonly hint = input('');
  readonly value = model.required<number>();

  protected readonly canDecrease = computed(() => this.value() > this.min());
  protected readonly canIncrease = computed(() => this.value() < this.max());

  protected step(delta: 1 | -1): void {
    const next = Math.min(this.max(), Math.max(this.min(), this.value() + delta));
    if (next !== this.value()) {
      this.value.set(next);
    }
  }
}
