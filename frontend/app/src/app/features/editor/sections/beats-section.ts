import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import type { Beat } from '@contract/api_responses';
import { replaceAt } from '@shared/game/campaign-edit';
import { DvField } from '@shared/ui/field/field';
import { fieldValue } from '@shared/ui/field/field-value';
import { DvInput } from '@shared/ui/field/input';
import { DvListEditor } from '@shared/ui/list-editor/list-editor';
import type { SelectOption } from '@shared/ui/select/select';
import { Sheet } from '@shared/ui/sheet/sheet';
import { CheckList } from '../components/check-list';
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
    CheckList,
    ConditionsEditor,
    DvField,
    DvInput,
    DvListEditor,
    ItemProblems,
    LinesField,
    NameIdFields,
  ],
  templateUrl: './beats-section.html',
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

  /** Os outros marcos, como opções de requisito. */
  protected others(beats: readonly Beat[], own: string): SelectOption[] {
    return beats.filter((b) => b.id !== own).map((b) => ({ value: b.id, label: b.title || b.id }));
  }

  protected async remove(index: number): Promise<void> {
    const beat = this.store.campaign()?.beats[index];
    if (beat === undefined) {
      return;
    }
    const ok = await confirmRemove(
      this.sheet,
      'Remover o marco',
      `Remover "${beat.title || beat.id}"? Os marcos que exigiam este perdem o requisito. As condições que citavam este marco ficam sem marco, e o editor avisa.`,
    );
    if (ok) {
      this.store.remove('beat', beat.id);
    }
  }
}
