import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

const MAX_PIPS = 24;

/** Pontos de vida: um ponto cheio por unidade atual e um vazio por unidade perdida. Texto alternativo com os números. */
@Component({
  selector: 'dv-pips',
  templateUrl: './pips.html',
  styleUrl: './pips.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { role: 'img', '[attr.aria-label]': 'description()' },
})
export class DvPips {
  readonly value = input.required<number>();
  readonly max = input.required<number>();
  readonly noun = input('pontos de vida');

  protected readonly description = computed(
    () => `${this.noun()}: ${this.value()} de ${this.max()}`,
  );
  protected readonly filled = computed(() => Math.min(MAX_PIPS, Math.max(0, this.value())));
  protected readonly empty = computed(() =>
    Math.max(0, Math.min(MAX_PIPS, this.max()) - this.filled()),
  );
  protected readonly range = (n: number): number[] => Array.from({ length: n }, (_, i) => i);
}
