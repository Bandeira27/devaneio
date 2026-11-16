import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/** Uma linha de rótulo e valor. */
export interface KeyValueItem {
  label: string;
  value: string;
}

/** Lista de pares rótulo e valor (cena, ficha) como `dl` semântico: o rótulo em nota, o valor em destaque. */
@Component({
  selector: 'dv-key-value',
  template: `
    <dl>
      @for (item of items(); track item.label) {
        <div class="row">
          <dt>{{ item.label }}</dt>
          <dd>{{ item.value }}</dd>
        </div>
      }
    </dl>
  `,
  styleUrl: './key-value.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DvKeyValue {
  readonly items = input.required<readonly KeyValueItem[]>();
}
