import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import type { Location } from '@contract/api_responses';
import { replaceAt } from '@shared/game/campaign-edit';
import { DvField } from '@shared/ui/field/field';
import { fieldValue } from '@shared/ui/field/field-value';
import { DvInput } from '@shared/ui/field/input';
import { DvListEditor } from '@shared/ui/list-editor/list-editor';
import type { SelectOption } from '@shared/ui/select/select';
import { Sheet } from '@shared/ui/sheet/sheet';
import { CheckList } from '../components/check-list';
import { confirmRemove } from '../components/confirm-remove';
import { LinesField } from '../components/lines-field';
import { NameIdFields } from '../components/name-id-fields';
import { EditorStore } from '../editor.store';

/** Os locais da campanha: nome, descrição, para onde se vai a partir de cada um e as notas privadas. */
@Component({
  selector: 'dv-locations-section',
  imports: [CheckList, DvField, DvInput, DvListEditor, LinesField, NameIdFields],
  templateUrl: './locations-section.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LocationsSection {
  protected readonly store = inject(EditorStore);
  private readonly sheet = inject(Sheet);
  protected readonly fieldValue = fieldValue;
  protected readonly nameOf = (location: Location): string => location.name || location.id;

  protected setName(index: number, location: Location, name: string): void {
    this.store.rename('location', location.id, name, (c) => ({
      ...c,
      locations: replaceAt(c.locations, index, { ...location, name }),
    }));
  }

  protected patch(index: number, location: Location, patch: Partial<Location>): void {
    this.store.replaceIn('locations', index, { ...location, ...patch });
  }

  /** Os outros locais, como opções de ligação. */
  protected others(locations: readonly Location[], own: string): SelectOption[] {
    return locations
      .filter((l) => l.id !== own)
      .map((l) => ({ value: l.id, label: l.name || l.id }));
  }

  protected async remove(index: number): Promise<void> {
    const location = this.store.campaign()?.locations[index];
    if (location === undefined) {
      return;
    }
    const ok = await confirmRemove(
      this.sheet,
      'Remover o local',
      `Remover "${location.name || location.id}"? As ligações para ele somem e os NPCs que estavam nele ficam sem local.`,
    );
    if (ok) {
      this.store.remove('location', location.id);
    }
  }
}
