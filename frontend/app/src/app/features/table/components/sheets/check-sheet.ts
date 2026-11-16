import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import type { RulesView } from '@contract/api_responses';
import { check } from '@shared/game/commands';
import { DvButton } from '@shared/ui/button/button';
import { DvField } from '@shared/ui/field/field';
import { DvInput } from '@shared/ui/field/input';
import { SHEET_DATA, SheetRef } from '@shared/ui/sheet/sheet';
import { fieldValue } from '@shared/ui/field/field-value';
import { DvSheetHead } from '@shared/ui/sheet/sheet-head';

/** O que a folha de testar recebe: o sistema de regras. */
export interface CheckSheetData {
  rules: RulesView;
}

/** Folha de testar uma habilidade: mostra a fórmula e devolve a linha de comando. */
@Component({
  selector: 'dv-check-sheet',
  imports: [DvSheetHead, DvButton, DvField, DvInput],
  template: `
    <dv-sheet-head title="Testar uma habilidade" />
    <form class="dv-stack" (submit)="$event.preventDefault(); ref.close(command())">
      <dv-field label="Habilidade" [hint]="formula()">
        <select dvInput [value]="skill()" (change)="skill.set(fieldValue($event))">
          @for (item of data.rules.skills; track item.id) {
            <option [value]="item.id">{{ item.name }}</option>
          }
        </select>
      </dv-field>
      <dv-field label="Dificuldade">
        <select dvInput [value]="difficulty()" (change)="difficulty.set(fieldValue($event))">
          @for (item of data.rules.difficulties; track item.id) {
            <option [value]="item.id">{{ item.name }} ({{ item.value }})</option>
          }
        </select>
      </dv-field>
      @if (data.rules.modifiers.length > 0) {
        <dv-field label="Modificador">
          <select dvInput [value]="modifier()" (change)="modifier.set(fieldValue($event))">
            <option value="">nenhum</option>
            @for (item of data.rules.modifiers; track item.id) {
              <option [value]="item.id">{{ item.name }} ({{ item.value }})</option>
            }
          </select>
        </dv-field>
      }
      <button dvButton="primary" type="submit">Testar</button>
    </form>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CheckSheet {
  protected readonly fieldValue = fieldValue;
  protected readonly data = inject(SHEET_DATA) as CheckSheetData;
  protected readonly ref = inject<SheetRef<string>>(SheetRef);

  protected readonly skill = signal(this.data.rules.skills[0]?.id ?? '');
  protected readonly difficulty = signal(
    (this.data.rules.difficulties.find((d) => d.id === 'normal') ?? this.data.rules.difficulties[0])
      ?.id ?? '',
  );
  protected readonly modifier = signal('');
  protected readonly formula = computed(() => {
    const found = this.data.rules.skills.find((s) => s.id === this.skill());
    return found ? `${found.formula}${found.description ? ` — ${found.description}` : ''}` : '';
  });
  protected readonly command = computed(() =>
    check(this.skill(), this.difficulty(), this.modifier()),
  );
}
