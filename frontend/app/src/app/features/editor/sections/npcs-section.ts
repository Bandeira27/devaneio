import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import type { Npc } from '@contract/api_responses';
import { replaceAt } from '@shared/game/campaign-edit';
import { ConfirmSheet } from '@shared/ui/confirm/confirm-sheet';
import { DvField } from '@shared/ui/field/field';
import { fieldValue } from '@shared/ui/field/field-value';
import { DvInput } from '@shared/ui/field/input';
import { DvListEditor } from '@shared/ui/list-editor/list-editor';
import { DvSelect, type SelectOption } from '@shared/ui/select/select';
import { Sheet } from '@shared/ui/sheet/sheet';
import { DvStepper } from '@shared/ui/stepper/stepper';
import { LinesField } from '../components/lines-field';
import { EditorStore } from '../editor.store';

const NONE: SelectOption = { value: '', label: '(nenhum)' };

/** Os NPCs: quem são, onde começam, de que facção, como tratam o grupo (disposição), a arma e as notas privadas. */
@Component({
  selector: 'dv-npcs-section',
  imports: [DvField, DvInput, DvListEditor, DvSelect, DvStepper, LinesField],
  templateUrl: './npcs-section.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class NpcsSection {
  protected readonly store = inject(EditorStore);
  private readonly sheet = inject(Sheet);
  protected readonly fieldValue = fieldValue;
  protected readonly nameOf = (npc: Npc): string => npc.name || npc.id;
  protected readonly locations = computed<SelectOption[]>(() => [
    NONE,
    ...(this.store.campaign()?.locations ?? []).map((l) => ({
      value: l.id,
      label: l.name || l.id,
    })),
  ]);
  protected readonly factions = computed<SelectOption[]>(() => [
    NONE,
    ...(this.store.campaign()?.factions ?? []).map((f) => ({ value: f.id, label: f.name || f.id })),
  ]);
  protected readonly weapons = computed<SelectOption[]>(() => [
    { value: '', label: '(a arma padrão do sistema)' },
    ...(this.store.rules()?.weapons ?? []).map((w) => ({ value: w.id, label: w.name })),
  ]);

  protected setName(index: number, npc: Npc, name: string): void {
    this.store.rename('npc', npc.id, name, (c) => ({
      ...c,
      npcs: replaceAt(c.npcs, index, { ...npc, name }),
    }));
  }

  protected patch(index: number, npc: Npc, patch: Partial<Npc>): void {
    this.store.replaceIn('npcs', index, { ...npc, ...patch });
  }

  protected async remove(index: number): Promise<void> {
    const npc = this.store.campaign()?.npcs[index];
    if (npc === undefined) {
      return;
    }
    const ok = await this.sheet.open<boolean>(ConfirmSheet, {
      label: 'Remover o NPC',
      data: {
        title: 'Remover o NPC',
        text: `Remover "${npc.name || npc.id}"? Os fatos que falavam dele ficam sem assunto.`,
        action: 'Remover',
      },
    });
    if (ok) {
      this.store.remove('npc', npc.id);
    }
  }
}
