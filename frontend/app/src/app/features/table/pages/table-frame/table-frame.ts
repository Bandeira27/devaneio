import { ChangeDetectionStrategy, Component, OnInit, inject, input } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { TableStore } from '../../table.store';

/**
 * O quadro de uma mesa: dono do `TableStore` e da leitura dela (a carga e o fluxo ao vivo). A mesa e o painel do
 * anfitrião são páginas filhas e usam o mesmo estado: ir de uma à outra e voltar não recarrega a mesa nem reabre o
 * fluxo, e o que se estava lendo continua onde estava.
 */
@Component({
  selector: 'dv-table-frame',
  imports: [RouterOutlet],
  providers: [TableStore],
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
