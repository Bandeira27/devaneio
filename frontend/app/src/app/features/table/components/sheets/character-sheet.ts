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
  templateUrl: './character-sheet.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CharacterSheet {
  protected readonly data = inject(SHEET_DATA) as CharacterSheetData;
}
