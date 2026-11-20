import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { DvDisclosure } from '@shared/ui/disclosure/disclosure';
import { DvField } from '@shared/ui/field/field';
import { fieldValue } from '@shared/ui/field/field-value';
import { DvInput } from '@shared/ui/field/input';
import { DvSelect, type SelectOption } from '@shared/ui/select/select';
import { EditorStore } from '../editor.store';

/** A visão geral da campanha: nome, premissa, onde o grupo começa e o sistema de regras. */
@Component({
  selector: 'dv-overview-section',
  imports: [DvDisclosure, DvField, DvInput, DvSelect],
  templateUrl: './overview-section.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class OverviewSection {
  protected readonly store = inject(EditorStore);
  protected readonly fieldValue = fieldValue;
  protected readonly locations = computed<SelectOption[]>(() =>
    (this.store.campaign()?.locations ?? []).map((l) => ({ value: l.id, label: l.name || l.id })),
  );
  protected readonly systems = computed<SelectOption[]>(() =>
    this.store.systems().map((system) => ({ value: system.id, label: system.name })),
  );

  protected set(patch: Partial<NonNullable<ReturnType<EditorStore['campaign']>>>): void {
    this.store.update((c) => ({ ...c, ...patch }));
  }
}
