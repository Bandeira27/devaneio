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
  template: `
    <dv-sheet-head title="Para onde ir?" />
    @if (data.exits.length === 0) {
      <p class="dv-note">Não há saídas daqui.</p>
      <dv-sheet-foot>
        <button dvButton type="button" cdkFocusInitial (click)="ref.close()">Fechar</button>
      </dv-sheet-foot>
    } @else {
      <form class="dv-stack" (submit)="$event.preventDefault(); ref.close(command())">
        <dv-choice legend="Destino" [options]="options" [(value)]="destination" />
        <p class="dv-note">O grupo todo se move. Gasta a sua ação.</p>
        <dv-sheet-foot>
          <button dvButton type="button" (click)="ref.close()">Cancelar</button>
          <button dvButton="primary" type="submit">Ir para {{ destinationName() }}</button>
        </dv-sheet-foot>
      </form>
    }
  `,
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
