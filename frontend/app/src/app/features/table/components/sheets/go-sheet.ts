import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { go } from '@shared/game/commands';
import { DvButton } from '@shared/ui/button/button';
import { DvChoice, type ChoiceOption } from '@shared/ui/choice/choice';
import { SHEET_DATA, SheetRef } from '@shared/ui/sheet/sheet';
import { DvSheetHead } from '@shared/ui/sheet/sheet-head';
import { DvSheetFoot } from '@shared/ui/sheet/sheet-foot';

/** O que a folha de ir recebe: as saídas do local. */
export interface GoSheetData {
  exits: { id: string; name: string }[];
  /** O destino já escolhido (tocado na cena): ele abre marcado. */
  preselect?: string;
}

/**
 * Folha de ir para outro local, em um passo só: as saídas como opções (a tocada na cena, ou a primeira, já marcada) e,
 * no rodapé, o botão que diz para onde o grupo vai. Ir move o grupo todo e gasta a ação, o que a nota avisa; devolve a
 * linha de comando.
 */
@Component({
  selector: 'dv-go-sheet',
  imports: [DvSheetHead, DvSheetFoot, DvButton, DvChoice],
  templateUrl: './go-sheet.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GoSheet {
  protected readonly data = inject(SHEET_DATA) as GoSheetData;
  protected readonly ref = inject<SheetRef<string>>(SheetRef);
  protected readonly options: ChoiceOption[] = this.data.exits.map((exit) => ({
    value: exit.id,
    label: exit.name,
  }));
  protected readonly destination = signal(
    (this.data.exits.find((exit) => exit.id === this.data.preselect) ?? this.data.exits[0])?.id ??
      '',
  );
  protected readonly destinationName = computed(
    () => this.data.exits.find((exit) => exit.id === this.destination())?.name ?? '',
  );
  protected readonly command = computed(() => go(this.destination()));
}
