import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import type { Faction } from '@contract/api_responses';
import { replaceAt } from '@shared/game/campaign-edit';
import { DvField } from '@shared/ui/field/field';
import { fieldValue } from '@shared/ui/field/field-value';
import { DvInput } from '@shared/ui/field/input';
import { DvListEditor } from '@shared/ui/list-editor/list-editor';
import { LinesField } from '../components/lines-field';
import { NameIdFields } from '../components/name-id-fields';
import { EditorStore } from '../editor.store';

/** As facções: grupos com metas próprias, a que os NPCs podem pertencer. */
@Component({
  selector: 'dv-factions-section',
  imports: [DvField, DvInput, DvListEditor, LinesField, NameIdFields],
  templateUrl: './factions-section.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FactionsSection {
  protected readonly store = inject(EditorStore);
  protected readonly fieldValue = fieldValue;
  protected readonly nameOf = (faction: Faction): string => faction.name || faction.id;

  protected setName(index: number, faction: Faction, name: string): void {
    this.store.rename('faction', faction.id, name, (c) => ({
      ...c,
      factions: replaceAt(c.factions, index, { ...faction, name }),
    }));
  }

  protected patch(index: number, faction: Faction, patch: Partial<Faction>): void {
    this.store.replaceIn('factions', index, { ...faction, ...patch });
  }

  protected remove(index: number): void {
    const faction = this.store.campaign()?.factions[index];
    if (faction === undefined) {
      return;
    }
    this.store.remove(
      'faction',
      faction.id,
      `Facção "${faction.name || faction.id}" removido. Os NPCs que pertenciam a ela ficam sem facção.`,
    );
  }
}
