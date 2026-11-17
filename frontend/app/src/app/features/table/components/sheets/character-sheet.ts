import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import type { Character, RulesView } from '@contract/api_responses';
import { SHEET_DATA } from '@shared/ui/sheet/sheet';
import { DvSheetHead } from '@shared/ui/sheet/sheet-head';
import { CharacterCard } from '../character-card/character-card';

/** O que a ficha recebe: o personagem e o sistema de regras. */
export interface CharacterSheetData {
  character: Character;
  rules: RulesView;
}

/** A folha "Ficha": a ficha do personagem (`dv-character-card`) numa folha, para o celular e a tela média. */
@Component({
  selector: 'dv-character-sheet',
  imports: [CharacterCard, DvSheetHead],
  template: `
    <dv-sheet-head [title]="data.character.name" />
    <dv-character-card [character]="data.character" [rules]="data.rules" />
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CharacterSheet {
  protected readonly data = inject(SHEET_DATA) as CharacterSheetData;
}
