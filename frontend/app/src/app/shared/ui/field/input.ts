import { Directive, signal } from '@angular/core';

let nextId = 0;

/** O `<input>`, `<textarea>` ou `<select>` de um `dv-field`: ele dá o id e recebe as descrições e o estado de erro. */
@Directive({
  selector: 'input[dvInput], textarea[dvInput], select[dvInput]',
  host: {
    class: 'dv-input',
    '[id]': 'id',
    '[attr.aria-describedby]': 'describedBy() || null',
    '[attr.aria-invalid]': "invalid() ? 'true' : null",
  },
})
export class DvInput {
  readonly id = `dv-input-${nextId++}`;
  readonly describedBy = signal('');
  readonly invalid = signal(false);
}
