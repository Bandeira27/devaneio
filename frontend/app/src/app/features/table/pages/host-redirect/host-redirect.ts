import { ChangeDetectionStrategy, Component, effect, inject, input } from '@angular/core';
import { Router } from '@angular/router';
import { HostSession } from '../../host/host-session';
import { TableStore } from '../../table.store';

/**
 * A rota antiga do painel (`/mesa/:id/anfitriao`): o painel agora é uma barra da própria mesa, então esta página só leva
 * para a mesa e, se quem chegou é o anfitrião, pede a barra aberta. Existe para não quebrar links guardados.
 */
@Component({
  selector: 'dv-host-redirect',
  template: '',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HostRedirect {
  readonly tableId = input.required<string>();

  private readonly store = inject(TableStore);
  private readonly session = inject(HostSession);
  private readonly router = inject(Router);

  constructor() {
    effect(() => {
      const state = this.store.state();
      if (state === 'ready' || state === 'failed') {
        if (state === 'ready' && this.store.isHost()) {
          this.session.requested.set(true);
        }
        void this.router.navigate(['/mesa', this.tableId()], { replaceUrl: true });
      }
    });
  }
}
