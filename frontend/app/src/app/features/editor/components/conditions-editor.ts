import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Injector,
  afterNextRender,
  computed,
  inject,
  input,
  model,
} from '@angular/core';
import {
  CONDITION_KINDS,
  conditionTarget,
  defaultCondition,
  withTarget,
  type Condition,
  type ConditionKind,
} from '@shared/game/campaign-edit';
import { DvButton } from '@shared/ui/button/button';
import { focusElement, isFocusFree } from '@shared/ui/focus';
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
  /** De quem é a lista ("marco Chegada"), para os botões repetidos terem nome próprio. */
  readonly owner = input('');
  /** O marco dono da lista: ele não pode depender da própria conclusão. */
  readonly ownBeatId = input('');
  readonly conditions = model.required<readonly Condition[]>();

  protected readonly store = inject(EditorStore);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly injector = inject(Injector);
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
      const next = defaultCondition('at_location', campaign, this.skillIds(), this.ownBeatId());
      this.conditions.update((list) => [...list, next]);
      this.focusAfterRender(() => this.rows().at(-1)?.querySelector<HTMLElement>('select'));
    }
  }

  protected remove(index: number): void {
    this.conditions.update((list) => list.filter((_, i) => i !== index));
    // O botão clicado some (ou passa a ser o da condição seguinte): o foco vai ao "Remover" que ocupou o lugar, ou ao "Acrescentar".
    this.focusAfterRender(
      () =>
        this.rows()[Math.min(index, this.rows().length - 1)]?.querySelector<HTMLElement>(
          '.row__remove',
        ) ?? this.host.nativeElement.querySelector<HTMLElement>('.add-condition'),
    );
  }

  protected setKind(index: number, kind: string): void {
    const campaign = this.store.campaign();
    if (campaign !== null) {
      const next = defaultCondition(
        kind as ConditionKind,
        campaign,
        this.skillIds(),
        this.ownBeatId(),
      );
      this.conditions.update((list) => list.map((c, i) => (i === index ? next : c)));
    }
  }

  protected setTarget(index: number, target: string): void {
    this.conditions.update((list) => list.map((c, i) => (i === index ? withTarget(c, target) : c)));
  }

  /** O rótulo do campo que escolhe o que a condição cita. */
  protected targetLabel(kind: ConditionKind): string {
    return {
      at_location: 'Local',
      npc_down: 'NPC',
      beat_done: 'Marco',
      check_passed: 'Habilidade',
      turn_at_least: 'Turno',
    }[kind];
  }

  /** O que se pode escolher para o tipo. */
  protected optionsFor(kind: ConditionKind): SelectOption[] {
    return {
      at_location: this.locations(),
      npc_down: this.npcs(),
      beat_done: this.beats(),
      check_passed: this.skills(),
      turn_at_least: [],
    }[kind];
  }

  protected turnOf(condition: Condition): number {
    return condition.kind === 'turn_at_least' ? condition.turn : 0;
  }

  protected name(condition: Condition, index: number): string {
    const kind = CONDITION_KINDS.find((k) => k.kind === condition.kind)?.label ?? condition.kind;
    return `condição ${index + 1} (${kind})`;
  }

  /** O que dizer quando não há o que escolher para o tipo (ou `''` se há). */
  protected emptyText(kind: ConditionKind): string {
    const none: Record<ConditionKind, [number, string]> = {
      at_location: [this.locations().length, 'Ainda não há locais. Crie um em Locais.'],
      npc_down: [this.npcs().length, 'Ainda não há NPCs. Crie um em NPCs.'],
      beat_done: [this.beats().length, 'Não há outro marco para citar. Crie um em Marcos.'],
      turn_at_least: [1, ''],
      check_passed: [
        this.skills().length,
        this.store.rules() === null
          ? 'O sistema de regras não carregou: confira em Visão geral.'
          : 'Este sistema de regras não tem habilidades.',
      ],
    };
    const [count, text] = none[kind];
    return count === 0 ? text : '';
  }

  /** O nome de um botão da lista, com a lista e de quem ela é (os mesmos botões se repetem pela página). */
  protected where(): string {
    return `${this.label().toLowerCase()}${this.owner() ? ` (${this.owner()})` : ''}`;
  }

  private rows(): HTMLElement[] {
    return Array.from(this.host.nativeElement.querySelectorAll<HTMLElement>('.row'));
  }

  private focusAfterRender(target: () => HTMLElement | null | undefined): void {
    afterNextRender(
      () => {
        const el = target();
        if (el && isFocusFree()) {
          focusElement(el);
        }
      },
      { injector: this.injector },
    );
  }

  private skillIds(): string[] {
    return (this.store.rules()?.skills ?? []).map((s) => s.id);
  }
}
