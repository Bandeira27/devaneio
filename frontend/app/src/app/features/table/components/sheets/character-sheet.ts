import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import type { Character, RulesView } from '@contract/api_responses';
import { DvButton } from '@shared/ui/button/button';
import { DvPips } from '@shared/ui/pips/pips';
import { SHEET_DATA, SheetRef } from '@shared/ui/sheet/sheet';

export interface CharacterSheetData {
  character: Character;
  rules: RulesView;
}

@Component({
  selector: 'dv-character-sheet',
  imports: [DvButton, DvPips],
  template: `
    <div class="dv-sheet__head">
      <h2 class="dv-title">{{ data.character.name }}</h2>
      <button dvButton type="button" (click)="ref.close()">Fechar</button>
    </div>
    <div class="dv-stack">
      <dv-pips [value]="data.character.hp" [max]="data.character.max_hp" />
      <dl>
        @for (attribute of data.rules.attributes; track attribute.id) {
          <div class="row">
            <dt class="dv-note">{{ attribute.name }}</dt>
            <dd>{{ data.character.attributes[attribute.id] ?? '—' }}</dd>
          </div>
        }
      </dl>
      <p class="dv-note">
        Inventário:
        {{ data.character.inventory.length > 0 ? data.character.inventory.join(', ') : 'vazio' }}
      </p>
    </div>
  `,
  styles: '.row { display: flex; justify-content: space-between; } dd { margin: 0; }',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CharacterSheet {
  protected readonly data = inject(SHEET_DATA) as CharacterSheetData;
  protected readonly ref = inject<SheetRef<void>>(SheetRef);
}
