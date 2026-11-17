import { ChangeDetectionStrategy, Component, OnInit, effect, inject, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { DvButton } from '@shared/ui/button/button';
import { DvDisclosure } from '@shared/ui/disclosure/disclosure';
import { DvField } from '@shared/ui/field/field';
import { DvInput } from '@shared/ui/field/input';
import { DvKeyValue } from '@shared/ui/key-value/key-value';
import { DvNotice } from '@shared/ui/notice/notice';
import { DvOrnament } from '@shared/ui/ornament/ornament';
import { DvSteps } from '@shared/ui/steps/steps';
import { DvState } from '@shared/ui/state/state';
import { DvStepper } from '@shared/ui/stepper/stepper';
import { CharacterStore } from '../../character.store';
import { fieldValue } from '@shared/ui/field/field-value';

/** Tela de criar o personagem: nome e atributos do sistema. */
@Component({
  selector: 'dv-character-page',
  imports: [
    RouterLink,
    DvButton,
    DvDisclosure,
    DvField,
    DvInput,
    DvKeyValue,
    DvNotice,
    DvOrnament,
    DvState,
    DvSteps,
    DvStepper,
  ],
  providers: [CharacterStore],
  templateUrl: './character-page.html',
  styleUrl: './character-page.css',
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
