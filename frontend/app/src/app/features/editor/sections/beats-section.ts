import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import type { Beat } from '@contract/api_responses';
import { replaceAt } from '@shared/game/campaign-edit';
import { DvField } from '@shared/ui/field/field';
import { fieldValue } from '@shared/ui/field/field-value';
import { DvInput } from '@shared/ui/field/input';
import { DvListEditor } from '@shared/ui/list-editor/list-editor';
import { Sheet } from '@shared/ui/sheet/sheet';
import { ConditionsEditor } from '../components/conditions-editor';
import { confirmRemove } from '../components/confirm-remove';
import { ItemProblems } from '../components/item-problems';
import { LinesField } from '../components/lines-field';
import { NameIdFields } from '../components/name-id-fields';
import { EditorStore } from '../editor.store';

/**
 * Os marcos da trama: o que precisa acontecer antes (requisitos), quando começam e quando terminam sozinhos (condições)
 * e as notas privadas. Marco sem condições só se move pelo anfitrião. O que o servidor disse de cada marco aparece nele.
 */
@Component({
  selector: 'dv-beats-section',
  imports: [
    ConditionsEditor,
    DvField,
    DvInput,
    DvListEditor,
    ItemProblems,
    LinesField,
    NameIdFields,
  ],
  templateUrl: './beats-section.html',
  styleUrl: './editor-sections.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BeatsSection {
  protected readonly store = inject(EditorStore);
  private readonly sheet = inject(Sheet);
  protected readonly fieldValue = fieldValue;
  protected readonly nameOf = (beat: Beat): string => beat.title || beat.id;

  protected setTitle(index: number, beat: Beat, title: string): void {
    this.store.rename('beat', beat.id, title, (c) => ({
      ...c,
      beats: replaceAt(c.beats, index, { ...beat, title }),
    }));
  }

  protected patch(index: number, beat: Beat, patch: Partial<Beat>): void {
    this.store.replaceIn('beats', index, { ...beat, ...patch });
  }

  protected toggle(index: number, beat: Beat, target: string, event: Event): void {
    const on = (event.target as HTMLInputElement).checked;
    const requires = on ? [...beat.requires, target] : beat.requires.filter((r) => r !== target);
    this.patch(index, beat, { requires });
  }

  protected async remove(index: number): Promise<void> {
    const beat = this.store.campaign()?.beats[index];
    if (beat === undefined) {
      return;
    }
    const ok = await confirmRemove(
      this.sheet,
      'Remover o marco',
      `Remover "${beat.title || beat.id}"? Os marcos que exigiam este perdem o requisito. Condições que o citam ficam apontando para um marco que não existe, e o editor avisa.`,
    );
    if (ok) {
      this.store.remove('beat', beat.id);
    }
  }
}
