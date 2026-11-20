import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { DvButton } from '@shared/ui/button/button';
import { ConfirmSheet } from '@shared/ui/confirm/confirm-sheet';
import { DvNotice } from '@shared/ui/notice/notice';
import { DvPlayClock } from '@shared/ui/play-clock/play-clock';
import { Sheet } from '@shared/ui/sheet/sheet';
import { TableStore } from '../table.store';

/**
 * A partida: o tempo de jogo e o que o anfitrião faz com ela. Iniciar (na sala de espera), pausar e retomar (a pausa trava
 * os jogadores e ele continua) e encerrar (definitivo, pede confirmação). Só mostra o que vale na fase em que a mesa está.
 */
@Component({
  selector: 'dv-lifecycle-tools',
  imports: [DvButton, DvNotice, DvPlayClock],
  templateUrl: './lifecycle-tools.html',
  styleUrl: './lifecycle-tools.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LifecycleTools {
  protected readonly store = inject(TableStore);
  private readonly sheet = inject(Sheet);

  protected async end(): Promise<void> {
    const ok = await this.sheet.open<boolean>(ConfirmSheet, {
      label: 'Encerrar a partida',
      data: {
        title: 'Encerrar a partida',
        text: 'Encerrar a partida para todos? Ninguém mais poderá agir e não dá para reabri-la. A história continua visível para ler.',
        action: 'Encerrar',
      },
    });
    if (ok) {
      await this.store.lifecycle('end');
    }
  }
}
