import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/** Provisório: a cena ao vivo entra na próxima parte. */
@Component({
  selector: 'dv-table-page',
  template: `
    <div class="dv-page">
      <h2 class="dv-title">Sua mesa</h2>
      <p class="dv-note">Mesa {{ tableId() }}</p>
    </div>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TablePage {
  readonly tableId = input.required<string>();
}
