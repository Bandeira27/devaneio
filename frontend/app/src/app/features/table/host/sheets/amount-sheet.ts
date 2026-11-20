import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import {
  CommandError,
  MAX_AMOUNT,
  MAX_SOURCE,
  heal,
  hurt,
  type AmountVerb,
} from '@shared/game/commands';
import type { ToolTarget } from '@shared/game/host';
import { DvButton } from '@shared/ui/button/button';
import { DvChoice, type ChoiceOption } from '@shared/ui/choice/choice';
import { DvField } from '@shared/ui/field/field';
import { fieldValue } from '@shared/ui/field/field-value';
import { DvInput } from '@shared/ui/field/input';
import { SHEET_DATA, SheetRef } from '@shared/ui/sheet/sheet';
import { DvSheetHead } from '@shared/ui/sheet/sheet-head';
import { DvSheetFoot } from '@shared/ui/sheet/sheet-foot';
import { DvStepper } from '@shared/ui/stepper/stepper';

/** O que a folha de ferir ou curar recebe: o verbo e os alvos possíveis. */
export interface AmountSheetData {
  verb: AmountVerb;
  targets: ToolTarget[];
}

export const AMOUNT_COPY = {
  ferir: { title: 'Ferir', action: 'Ferir', source: 'a queda, uma armadilha' },
  curar: { title: 'Curar', action: 'Curar', source: 'uma poção, uma magia' },
} as const;

/** Folha de ferir ou curar à mão: alvo, quantia e, se quiser, a fonte que vai para o registro. Devolve a linha. */
@Component({
  selector: 'dv-amount-sheet',
  imports: [DvSheetHead, DvSheetFoot, DvButton, DvChoice, DvField, DvInput, DvStepper],
  template: `
    <dv-sheet-head [title]="copy.title" />
    @if (data.targets.length === 0) {
      <p class="dv-note">Não há ninguém para {{ data.verb }}.</p>
    } @else {
      <form class="dv-stack" (submit)="$event.preventDefault(); send()">
        <dv-choice legend="Quem" [options]="options()" [(value)]="target" />
        <dv-stepper label="Quantia" [min]="1" [max]="maxAmount" [(value)]="amount" />
        <dv-field
          label="Fonte (opcional)"
          [hint]="'Aparece no registro: ' + copy.source + '.'"
          [error]="error()"
        >
          <input
            dvInput
            type="text"
            autocomplete="off"
            [attr.maxlength]="max"
            [value]="source()"
            (input)="source.set(fieldValue($event))"
          />
        </dv-field>
        <dv-sheet-foot>
          <button dvButton="primary" type="submit">{{ copy.action }}</button>
        </dv-sheet-foot>
      </form>
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AmountSheet {
  protected readonly data = inject(SHEET_DATA) as AmountSheetData;
  protected readonly ref = inject<SheetRef<string>>(SheetRef);
  protected readonly copy = AMOUNT_COPY[this.data.verb];
  protected readonly fieldValue = fieldValue;
  protected readonly max = MAX_SOURCE;
  protected readonly maxAmount = MAX_AMOUNT;
  protected readonly target = signal(this.data.targets[0]?.id ?? '');
  protected readonly amount = signal(1);
  protected readonly source = signal('');
  protected readonly error = signal('');
  protected readonly options = computed<ChoiceOption[]>(() =>
    this.data.targets.map((t) => ({
      value: t.id,
      label: t.name,
      detail: t.kind === 'npc' ? 'NPC' : 'Personagem',
    })),
  );

  protected send(): void {
    try {
      const build = this.data.verb === 'ferir' ? hurt : heal;
      this.ref.close(build(this.target(), this.amount(), this.source()));
    } catch (error) {
      this.error.set(
        error instanceof CommandError ? error.message : 'Não foi possível montar o comando.',
      );
    }
  }
}
