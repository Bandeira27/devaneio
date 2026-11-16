import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import type { RulesView } from '@contract/api_responses';
import { check } from '@shared/game/commands';
import { DvButton } from '@shared/ui/button/button';
import { DvField } from '@shared/ui/field/field';
import { DvInput } from '@shared/ui/field/input';
import { SHEET_DATA, SheetRef } from '@shared/ui/sheet/sheet';

export interface CheckSheetData {
  rules: RulesView;
}

@Component({
  selector: 'dv-check-sheet',
  imports: [DvButton, DvField, DvInput],
  template: `
    <div class="dv-sheet__head">
      <h2 class="dv-title">Testar uma habilidade</h2>
      <button dvButton type="button" (click)="ref.close()">Fechar</button>
    </div>
    <form class="dv-stack" (submit)="$event.preventDefault(); ref.close(command())">
      <dv-field label="Habilidade" [hint]="formula()">
        <select dvInput [value]="skill()" (change)="skill.set(value($event))">
          @for (item of data.rules.skills; track item.id) {
            <option [value]="item.id">{{ item.name }}</option>
          }
        </select>
      </dv-field>
      <dv-field label="Dificuldade">
        <select dvInput [value]="difficulty()" (change)="difficulty.set(value($event))">
          @for (item of data.rules.difficulties; track item.id) {
            <option [value]="item.id">{{ item.name }} ({{ item.value }})</option>
          }
        </select>
      </dv-field>
      @if (data.rules.modifiers.length > 0) {
        <dv-field label="Modificador">
          <select dvInput [value]="modifier()" (change)="modifier.set(value($event))">
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

  protected value(event: Event): string {
    return (event.target as HTMLSelectElement).value;
  }
}
