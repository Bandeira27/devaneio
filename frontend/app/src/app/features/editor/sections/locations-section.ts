import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import type { Location } from '@contract/api_responses';
import { replaceAt } from '@shared/game/campaign-edit';
import { ConfirmSheet } from '@shared/ui/confirm/confirm-sheet';
import { DvField } from '@shared/ui/field/field';
import { fieldValue } from '@shared/ui/field/field-value';
import { DvInput } from '@shared/ui/field/input';
import { DvListEditor } from '@shared/ui/list-editor/list-editor';
import { Sheet } from '@shared/ui/sheet/sheet';
import { LinesField } from '../components/lines-field';
import { EditorStore } from '../editor.store';

/** Os locais da campanha: nome, descrição, para onde se vai a partir de cada um e as notas privadas. */
@Component({
  selector: 'dv-locations-section',
  imports: [DvField, DvInput, DvListEditor, LinesField],
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
    const ok = await this.sheet.open<boolean>(ConfirmSheet, {
      label: 'Remover o local',
      data: {
        title: 'Remover o local',
        text: `Remover "${location.name || location.id}"? As ligações para ele somem e os NPCs que estavam nele ficam sem local.`,
        action: 'Remover',
      },
    });
    if (ok) {
      this.store.remove('location', location.id);
    }
  }
}
