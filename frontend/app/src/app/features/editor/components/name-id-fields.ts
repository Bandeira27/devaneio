import {
  ChangeDetectionStrategy,
  Component,
  effect,
  inject,
  input,
  output,
  signal,
} from '@angular/core';
import type { ItemKind } from '@shared/game/campaign-edit';
import { DvDisclosure } from '@shared/ui/disclosure/disclosure';
import { DvField } from '@shared/ui/field/field';
import { fieldValue } from '@shared/ui/field/field-value';
import { DvInput } from '@shared/ui/field/input';
import { EditorStore } from '../editor.store';

/**
 * O nome e o identificador de um item (local, NPC, facção). O id acompanha o nome enquanto o autor não o escreve; ao
 * escrevê-lo, vale quando ele confirma (sai do campo ou aperta Enter), não a cada tecla: um valor no meio do caminho
 * poderia igualar o id de outro item e fundir os dois. Id vazio ou repetido é recusado com a frase, e o campo volta ao
 * valor de antes.
 */
@Component({
  selector: 'dv-name-id-fields',
  imports: [DvDisclosure, DvField, DvInput],
  template: `
    <dv-field [label]="label()" [announce]="false" [error]="store.errorAt(path() + '.' + field())">
      @if (multiline()) {
        <textarea
          dvInput
          rows="3"
          [value]="name()"
          (input)="nameChange.emit(fieldValue($event))"
        ></textarea>
      } @else {
        <input dvInput type="text" [value]="name()" (input)="nameChange.emit(fieldValue($event))" />
      }
    </dv-field>
    <dv-disclosure label="Avançado: identificador" [(open)]="advancedOpen">
      <dv-field
        label="Identificador"
        [announce]="false"
        [hint]="
          store.isAuto(kind(), id())
            ? 'Acompanha ' + follows() + '. Escreva aqui para fixar outro.'
            : 'Letras minúsculas sem acento, números, - e _.'
        "
        [error]="idError() || store.errorAt(path() + '.id')"
      >
        <input dvInput type="text" [value]="id()" (change)="commit($event)" />
      </dv-field>
    </dv-disclosure>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class NameIdFields {
  /** O campo do identificador abre sozinho quando há erro nele e não fecha sozinho depois. */
  protected readonly advancedOpen = signal(false);

  constructor() {
    effect(() => {
      if (this.idError() || this.store.errorAt(this.path() + '.id')) {
        this.advancedOpen.set(true);
      }
    });
  }

  readonly kind = input.required<ItemKind>();
  readonly id = input.required<string>();
  readonly name = input.required<string>();
  /** O rótulo do campo do nome ("Nome"; "Título" nos marcos). */
  readonly label = input('Nome');
  /** O campo do nome no JSON (`name`; `title` nos marcos), para achar o erro dele. */
  readonly field = input('name');
  /** O campo do nome é uma caixa de várias linhas (o texto de um fato)? */
  readonly multiline = input(false);
  /** O que o id acompanha, na dica ("o nome"; "o texto"). */
  readonly follows = input('o nome');
  /** Onde o item está na campanha (`locations.2`), para achar os erros dele. */
  readonly path = input.required<string>();
  readonly nameChange = output<string>();

  protected readonly store = inject(EditorStore);
  protected readonly fieldValue = fieldValue;
  protected readonly idError = signal('');

  protected commit(event: Event): void {
    const input = event.target as HTMLInputElement;
    const problem = this.store.setId(this.kind(), this.id(), input.value.trim());
    this.idError.set(problem);
    if (problem !== '') {
      input.value = this.id();
    }
  }
}
