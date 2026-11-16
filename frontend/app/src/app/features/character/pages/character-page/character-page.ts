import { ChangeDetectionStrategy, Component, OnInit, effect, inject, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { DvButton } from '@shared/ui/button/button';
import { DvField } from '@shared/ui/field/field';
import { DvInput } from '@shared/ui/field/input';
import { DvNotice } from '@shared/ui/notice/notice';
import { DvStepper } from '@shared/ui/stepper/stepper';
import { CharacterStore } from '../../character.store';
import { fieldValue } from '@shared/ui/field/field-value';

@Component({
  selector: 'dv-character-page',
  imports: [RouterLink, DvButton, DvField, DvInput, DvNotice, DvStepper],
  providers: [CharacterStore],
  templateUrl: './character-page.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CharacterPage implements OnInit {
  protected readonly fieldValue = fieldValue;
  readonly tableId = input.required<string>();

  protected readonly store = inject(CharacterStore);

  constructor() {
    effect(() => this.store.tableId.set(this.tableId()));
  }

  ngOnInit(): void {
    this.store.tableId.set(this.tableId()); // os inputs já chegaram; o effect só roda depois
    void this.store.load();
  }
}
