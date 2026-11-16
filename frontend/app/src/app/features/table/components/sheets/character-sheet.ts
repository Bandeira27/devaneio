import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import type { Character, RulesView } from '@contract/api_responses';
import { DvPips } from '@shared/ui/pips/pips';
import { SHEET_DATA } from '@shared/ui/sheet/sheet';
import { DvSheetHead } from '@shared/ui/sheet/sheet-head';

export interface CharacterSheetData {
  character: Character;
  rules: RulesView;
}

@Component({
  selector: 'dv-character-sheet',
  imports: [DvSheetHead, DvPips],
  template: `
    <dv-sheet-head title="{{ data.character.name }}" />
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
}
