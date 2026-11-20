import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { END_TURN, REST, type AmountVerb } from '@shared/game/commands';
import { DvButton } from '@shared/ui/button/button';
import { ConfirmSheet } from '@shared/ui/confirm/confirm-sheet';
import { Sheet } from '@shared/ui/sheet/sheet';
import { TableStore } from '../table.store';
import { AMOUNT_COPY, AmountSheet } from './sheets/amount-sheet';

/**
 * As ferramentas do turno do anfitrião: fim do turno e descansar (pedem confirmação, mexem com o grupo todo) e ferir e
 * curar à mão (alvo, quantia e fonte). Cada uma monta a linha de comando que o servidor já conhece.
 */
@Component({
  selector: 'dv-turn-tools',
  imports: [DvButton],
  templateUrl: './turn-tools.html',
  styleUrl: './turn-tools.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TurnTools {
  protected readonly store = inject(TableStore);
  private readonly sheet = inject(Sheet);

  protected async endTurn(): Promise<void> {
    const ok = await this.sheet.open<boolean>(ConfirmSheet, {
      label: 'Fim do turno',
      data: {
        title: 'Fim do turno',
        text: `Encerra o turno ${this.store.turn()} para todos: o diretor age e os NPCs hostis reagem.`,
        action: 'Encerrar o turno',
      },
    });
    if (ok) {
      await this.store.run(END_TURN);
    }
  }

  protected async rest(): Promise<void> {
    const ok = await this.sheet.open<boolean>(ConfirmSheet, {
      label: 'Descansar',
      data: {
        title: 'Descansar',
        text: 'O grupo recupera a vida e o turno passa, como no fim do turno.',
        action: 'Descansar',
      },
    });
    if (ok) {
      await this.store.run(REST);
    }
  }

  protected async amount(verb: AmountVerb): Promise<void> {
    const line = await this.sheet.open<string>(AmountSheet, {
      label: AMOUNT_COPY[verb].title,
      data: { verb, targets: this.store.host()?.targets ?? [] },
    });
    if (line) {
      await this.store.run(line);
    }
  }
}
