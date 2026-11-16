import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import type { Character, RulesView } from '@contract/api_responses';
import { DvKeyValue, type KeyValueItem } from '@shared/ui/key-value/key-value';
import { DvPips } from '@shared/ui/pips/pips';
import { SHEET_DATA } from '@shared/ui/sheet/sheet';
import { DvSheetHead } from '@shared/ui/sheet/sheet-head';

/** O que a ficha recebe: o personagem e o sistema de regras. */
export interface CharacterSheetData {
  character: Character;
  rules: RulesView;
}

/** Ficha do personagem: hp, atributos e inventário (os itens que são armas aparecem pelo nome da arma). */
@Component({
  selector: 'dv-character-sheet',
  imports: [DvKeyValue, DvSheetHead, DvPips],
  template: `
    <dv-sheet-head [title]="data.character.name" />
    <div class="dv-stack">
      <dv-pips [value]="data.character.hp" [max]="data.character.max_hp" />
      <dv-key-value [items]="items()" />
    </div>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CharacterSheet {
  protected readonly data = inject(SHEET_DATA) as CharacterSheetData;
  protected readonly items = computed<KeyValueItem[]>(() => {
    const { character, rules } = this.data;
    const weapon = (id: string): string => rules.weapons.find((w) => w.id === id)?.name ?? id;
    return [
      ...rules.attributes.map((a) => ({
        label: a.name,
        value: String(character.attributes[a.id] ?? '—'),
      })),
      {
        label: 'Inventário',
        value:
          character.inventory.length > 0 ? character.inventory.map(weapon).join(', ') : 'vazio',
      },
    ];
  });
}
