import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { DvField } from '@shared/ui/field/field';
import { fieldValue } from '@shared/ui/field/field-value';
import { DvInput } from '@shared/ui/field/input';
import { DvSelect, type SelectOption } from '@shared/ui/select/select';
import { EditorStore } from '../editor.store';

/** A visão geral da campanha: nome, premissa, onde o grupo começa e o sistema de regras. */
@Component({
  selector: 'dv-overview-section',
  imports: [DvField, DvInput, DvSelect],
  template: `
    @if (store.campaign(); as c) {
      <section class="dv-card dv-stack" aria-labelledby="geral-titulo">
        <h2 id="geral-titulo" class="dv-section">Visão geral</h2>
        <dv-field label="Título" [error]="store.errorAt('title')">
          <input
            dvInput
            type="text"
            [value]="c.title"
            (input)="set({ title: fieldValue($event) })"
          />
        </dv-field>
        <dv-field
          label="Premissa"
          hint="O que os jogadores leem antes de começar."
          [error]="store.errorAt('premise')"
        >
          <textarea
            dvInput
            rows="3"
            [value]="c.premise"
            (input)="set({ premise: fieldValue($event) })"
          ></textarea>
        </dv-field>
        @if (store.isNew()) {
          <dv-field
            label="Identificador"
            hint="Vira o nome do arquivo. Letras minúsculas sem acento, números, - e _."
            [error]="store.errorAt('id')"
          >
            <input dvInput type="text" [value]="c.id" (input)="set({ id: fieldValue($event) })" />
          </dv-field>
        } @else {
          <p class="dv-note">Identificador: {{ c.id }} (não muda depois de gravada)</p>
        }
        <dv-select
          label="Onde o grupo começa"
          [options]="locations()"
          [value]="c.start_location_id"
          [error]="store.errorAt('start_location_id')"
          (valueChange)="set({ start_location_id: $event })"
        />
        <dv-select
          label="Sistema de regras"
          hint="Atributos, habilidades e armas que a campanha usa."
          [options]="systems()"
          [value]="c.rules_id"
          [error]="store.errorAt('rules_id')"
          (valueChange)="set({ rules_id: $event })"
        />
      </section>
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class OverviewSection {
  protected readonly store = inject(EditorStore);
  protected readonly fieldValue = fieldValue;
  protected readonly locations = computed<SelectOption[]>(() =>
    (this.store.campaign()?.locations ?? []).map((l) => ({ value: l.id, label: l.name || l.id })),
  );
  protected readonly systems = computed<SelectOption[]>(() => {
    const own = this.store.campaign()?.rules_id ?? '';
    const options = this.store.systems().map((s) => ({ value: s.id, label: s.name }));
    // O sistema citado pode não existir (o validador avisa): a opção continua lá para não trocar o valor sem o autor ver.
    return options.some((o) => o.value === own) || own === ''
      ? options
      : [{ value: own, label: `${own} (não encontrado)` }, ...options];
  });

  protected set(patch: Partial<NonNullable<ReturnType<EditorStore['campaign']>>>): void {
    this.store.update((c) => ({ ...c, ...patch }));
  }
}
