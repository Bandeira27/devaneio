import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import type { Location } from '@contract/api_responses';
import { replaceAt } from '@shared/game/campaign-edit';
import { DvField } from '@shared/ui/field/field';
import { fieldValue } from '@shared/ui/field/field-value';
import { DvInput } from '@shared/ui/field/input';
import { DvListEditor } from '@shared/ui/list-editor/list-editor';
import { Sheet } from '@shared/ui/sheet/sheet';
import { confirmRemove } from '../components/confirm-remove';
import { LinesField } from '../components/lines-field';
import { NameIdFields } from '../components/name-id-fields';
import { EditorStore } from '../editor.store';

/** Os locais da campanha: nome, descrição, para onde se vai a partir de cada um e as notas privadas. */
@Component({
  selector: 'dv-locations-section',
  imports: [DvField, DvInput, DvListEditor, LinesField, NameIdFields],
  templateUrl: './locations-section.html',
  styleUrl: './editor-sections.css',
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

  protected toggle(index: number, location: Location, target: string, event: Event): void {
    const on = (event.target as HTMLInputElement).checked;
    const connections = on
      ? [...location.connections, target]
      : location.connections.filter((c) => c !== target);
    this.patch(index, location, { connections });
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
