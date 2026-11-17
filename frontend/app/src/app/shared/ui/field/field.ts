import {
  ChangeDetectionStrategy,
  Component,
  computed,
  contentChild,
  effect,
  input,
} from '@angular/core';
import { DvInput } from './input';

/** Rótulo, campo, dica e erro juntos: o rótulo aponta para o campo e a dica e o erro viram `aria-describedby`. */
@Component({
  selector: 'dv-field',
  templateUrl: './field.html',
  styleUrl: './field.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DvField {
  readonly label = input.required<string>();
  readonly hint = input('');
  readonly error = input('');
  /** O erro é anunciado na hora (`role="alert"`)? Falso onde ele muda sozinho a cada edição (o editor): fica ligado ao campo. */
  readonly announce = input(true);
  protected readonly role = computed(() => (this.announce() ? 'alert' : null));
  readonly control = contentChild.required(DvInput);

  constructor() {
    effect(() => {
      const control = this.control();
      const ids = [
        this.hint() ? `${control.id}-hint` : '',
        this.error() ? `${control.id}-error` : '',
      ].filter(Boolean);
      control.describedBy.set(ids.join(' '));
      control.invalid.set(this.error() !== '');
    });
  }
}
