import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import type { RulesView } from '@contract/api_responses';
import { modifierOptions } from '@shared/game/modifiers';
import { check } from '@shared/game/commands';
import { humanizeFormula } from '@shared/game/rules';
import { DvButton } from '@shared/ui/button/button';
import { DvChoice, type ChoiceOption } from '@shared/ui/choice/choice';
import { SHEET_DATA, SheetRef } from '@shared/ui/sheet/sheet';
import { DvSheetHead } from '@shared/ui/sheet/sheet-head';

/** O que a folha de testar recebe: o sistema de regras. */
export interface CheckSheetData {
  rules: RulesView;
}

/**
 * Folha de testar uma habilidade: a pessoa escolhe a habilidade, a dificuldade (pelo nome; o número só aparece no
 * detalhe) e, se houver, um modificador. Devolve a linha de comando.
 */
@Component({
  selector: 'dv-check-sheet',
  imports: [DvSheetHead, DvButton, DvChoice],
  template: `
    <dv-sheet-head title="Testar" />
    <form class="dv-stack" (submit)="$event.preventDefault(); ref.close(command())">
      <dv-choice legend="Habilidade" [options]="skills()" [(value)]="skill" />
      <dv-choice legend="Dificuldade" [options]="difficulties()" [(value)]="difficulty" />
      @if (data.rules.modifiers.length > 0) {
        <dv-choice legend="Modificador" [options]="modifiers()" [(value)]="modifier" />
      }
      <div class="dv-sheet__foot">
        <button dvButton="primary" type="submit">Testar</button>
      </div>
    </form>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CheckSheet {
  protected readonly data = inject(SHEET_DATA) as CheckSheetData;
  protected readonly ref = inject<SheetRef<string>>(SheetRef);

  protected readonly skill = signal(this.data.rules.skills[0]?.id ?? '');
  protected readonly difficulty = signal(
    (this.data.rules.difficulties.find((d) => d.id === 'normal') ?? this.data.rules.difficulties[0])
      ?.id ?? '',
  );
  protected readonly modifier = signal('');

  protected readonly skills = computed<ChoiceOption[]>(() =>
    this.data.rules.skills.map((s) => ({
      value: s.id,
      label: s.name,
      detail: `Rola ${humanizeFormula(s.formula, this.data.rules.attributes)}`,
    })),
  );
  protected readonly difficulties = computed<ChoiceOption[]>(() =>
    this.data.rules.difficulties.map((d) => ({
      value: d.id,
      label: d.name,
      detail: `Precisa de ${d.value}`,
    })),
  );
  protected readonly modifiers = computed(() => modifierOptions(this.data.rules.modifiers));
  protected readonly command = computed(() =>
    check(this.skill(), this.difficulty(), this.modifier()),
  );
}
