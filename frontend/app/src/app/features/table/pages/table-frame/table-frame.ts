import { ChangeDetectionStrategy, Component, OnInit, inject, input } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { HostSession } from '../../host/host-session';
import { TableStore } from '../../table.store';

/**
 * O quadro de uma mesa: dono do `TableStore`, da `HostSession` (a barra do anfitrião) e da leitura dela (a carga e o fluxo ao vivo). A mesa e a rota
 * antiga do painel são páginas filhas e usam o mesmo estado: trocar de uma à outra não recarrega a mesa nem reabre o
 * fluxo.
 */
@Component({
  selector: 'dv-table-frame',
  imports: [RouterOutlet],
  providers: [TableStore, HostSession],
  template: '<router-outlet />',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TableFrame implements OnInit {
  /** O id da mesa, da rota `/mesa/:tableId`. */
  readonly tableId = input.required<string>();

  private readonly store = inject(TableStore);

  ngOnInit(): void {
    this.store.tableId.set(this.tableId());
    void this.store.load();
  }
}
