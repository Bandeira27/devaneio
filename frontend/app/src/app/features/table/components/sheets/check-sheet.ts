import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import type { RulesView } from '@contract/api_responses';
import { modifierOptions } from '@shared/game/modifiers';
import { check } from '@shared/game/commands';
import { humanizeFormula } from '@shared/game/rules';
import { DvButton } from '@shared/ui/button/button';
import { DvDisclosure } from '@shared/ui/disclosure/disclosure';
import { DvChoice, type ChoiceOption } from '@shared/ui/choice/choice';
import { SHEET_DATA, SheetRef } from '@shared/ui/sheet/sheet';
import { DvSheetHead } from '@shared/ui/sheet/sheet-head';
import { DvSheetFoot } from '@shared/ui/sheet/sheet-foot';

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
  imports: [DvSheetHead, DvSheetFoot, DvButton, DvChoice, DvDisclosure],
  templateUrl: './check-sheet.html',
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
  /** O que está valendo, em poucas palavras, no resumo do "Ajustar" (o caminho comum é não mexer). */
  protected readonly summary = computed(() => {
    const difficulty =
      this.data.rules.difficulties.find((d) => d.id === this.difficulty())?.name ?? '';
    const modifier = this.data.rules.modifiers.find((m) => m.id === this.modifier())?.name;
    return modifier ? `${difficulty}, ${modifier}` : `${difficulty}, sem modificador`;
  });

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
