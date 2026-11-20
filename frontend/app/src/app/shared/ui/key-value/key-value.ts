import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/** Uma linha de rótulo e valor. */
export interface KeyValueItem {
  label: string;
  value: string;
}

/** Lista de pares rótulo e valor (cena, ficha) como `dl` semântico: o rótulo em nota, o valor em destaque. */
@Component({
  selector: 'dv-key-value',
  templateUrl: './key-value.html',
  styleUrl: './key-value.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DvKeyValue {
  readonly items = input.required<readonly KeyValueItem[]>();
}
