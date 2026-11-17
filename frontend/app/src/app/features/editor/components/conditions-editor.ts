import { ChangeDetectionStrategy, Component, computed, inject, input, model } from '@angular/core';
import {
  CONDITION_KINDS,
  conditionTarget,
  defaultCondition,
  withTarget,
  type Condition,
  type ConditionKind,
} from '@shared/game/campaign-edit';
import { DvButton } from '@shared/ui/button/button';
import { DvSelect, type SelectOption } from '@shared/ui/select/select';
import { DvStepper } from '@shared/ui/stepper/stepper';
import { EditorStore } from '../editor.store';

const KINDS: SelectOption[] = CONDITION_KINDS.map((k) => ({ value: k.kind, label: k.label }));

/**
 * As condições de um marco ou de um fato, em linhas: o tipo (lista fechada), o que ele cita (um item que existe:
 * local, NPC, marco ou habilidade do sistema) ou o número do turno. Todas as condições da lista precisam valer. Trocar
 * o tipo recomeça a condição no primeiro item que existe. Quem muda a lista é o pai (`conditions` é de duas vias).
 */
@Component({
  selector: 'dv-conditions-editor',
  imports: [DvButton, DvSelect, DvStepper],
  templateUrl: './conditions-editor.html',
  styleUrl: './conditions-editor.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ConditionsEditor {
  /** O título do bloco ("Para ativar"). */
  readonly label = input.required<string>();
  /** O que a lista vazia significa. */
  readonly hint = input('');
  /** Onde a lista está (`beats.0.activate_when`), para achar os erros de cada condição. */
  readonly path = input.required<string>();
  /** O marco dono da lista: ele não pode depender da própria conclusão. */
  readonly ownBeatId = input('');
  readonly conditions = model.required<readonly Condition[]>();

  protected readonly store = inject(EditorStore);
  protected readonly kinds = KINDS;
  protected readonly target = conditionTarget;
  protected readonly locations = computed<SelectOption[]>(() =>
    (this.store.campaign()?.locations ?? []).map((l) => ({ value: l.id, label: l.name || l.id })),
  );
  protected readonly npcs = computed<SelectOption[]>(() =>
    (this.store.campaign()?.npcs ?? []).map((n) => ({ value: n.id, label: n.name || n.id })),
  );
  protected readonly beats = computed<SelectOption[]>(() =>
    (this.store.campaign()?.beats ?? [])
      .filter((b) => b.id !== this.ownBeatId())
      .map((b) => ({ value: b.id, label: b.title || b.id })),
  );
  protected readonly skills = computed<SelectOption[]>(() =>
    (this.store.rules()?.skills ?? []).map((s) => ({ value: s.id, label: s.name })),
  );

  protected add(): void {
    const campaign = this.store.campaign();
    if (campaign !== null) {
      this.conditions.update((list) => [
        ...list,
        defaultCondition('at_location', campaign, this.skillIds()),
      ]);
    }
  }

  protected remove(index: number): void {
    this.conditions.update((list) => list.filter((_, i) => i !== index));
  }

  protected setKind(index: number, kind: string): void {
    const campaign = this.store.campaign();
    if (campaign !== null) {
      const next = defaultCondition(kind as ConditionKind, campaign, this.skillIds());
      this.conditions.update((list) => list.map((c, i) => (i === index ? next : c)));
    }
  }

  protected setTarget(index: number, target: string): void {
    this.conditions.update((list) => list.map((c, i) => (i === index ? withTarget(c, target) : c)));
  }

  protected turnOf(condition: Condition): number {
    return condition.kind === 'turn_at_least' ? condition.turn : 0;
  }

  protected name(condition: Condition, index: number): string {
    const kind = CONDITION_KINDS.find((k) => k.kind === condition.kind)?.label ?? condition.kind;
    return `condição ${index + 1} (${kind})`;
  }

  private skillIds(): string[] {
    return (this.store.rules()?.skills ?? []).map((s) => s.id);
  }
}
