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
  template: `
    <section class="dv-card dv-stack" aria-labelledby="partida-titulo">
      <h2 id="partida-titulo" class="dv-section">Partida</h2>
      <dv-play-clock
        [phase]="store.phase()"
        [seconds]="store.playClock().seconds"
        [receivedAt]="store.playClock().receivedAt"
      />
      @if (store.phase() === 'lobby') {
        <p class="dv-note">A história ainda não começou: a mesa está na sala de espera.</p>
      } @else if (store.phase() === 'paused') {
        <p class="dv-note">Pausada: os jogadores só leem. Você ainda pode agir.</p>
      } @else if (store.phase() === 'ended') {
        <p class="dv-note">Encerrada: ninguém mais age. A história fica para ler.</p>
      }
      @if (store.lifecycleError()) {
        <dv-notice kind="error">{{ store.lifecycleError() }}</dv-notice>
      }
      @if (store.phase() !== 'ended') {
        <div class="tools">
          @switch (store.phase()) {
            @case ('lobby') {
              <button
                dvButton="primary"
                type="button"
                [dvLoading]="store.lifecycleBusy()"
                [dvBlocked]="store.party().length === 0"
                [attr.aria-describedby]="store.party().length === 0 ? 'sem-personagem' : null"
                (click)="store.lifecycle('start')"
              >
                Iniciar campanha
              </button>
            }
            @case ('running') {
              <button
                dvButton
                type="button"
                [dvLoading]="store.lifecycleBusy()"
                (click)="store.lifecycle('pause')"
              >
                Pausar
              </button>
            }
            @case ('paused') {
              <button
                dvButton="primary"
                type="button"
                [dvLoading]="store.lifecycleBusy()"
                (click)="store.lifecycle('resume')"
              >
                Retomar
              </button>
            }
          }
          <button
            dvButton="danger"
            type="button"
            [dvBlocked]="store.lifecycleBusy()"
            (click)="end()"
          >
            Encerrar a partida
          </button>
        </div>
        @if (store.phase() === 'lobby' && store.party().length === 0) {
          <p id="sem-personagem" class="dv-note">Crie ao menos um personagem para iniciar.</p>
        }
      }
    </section>
  `,
  styles: `
    .tools {
      display: flex;
      flex-wrap: wrap;
      gap: var(--dv-space-2);
    }
  `,
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
