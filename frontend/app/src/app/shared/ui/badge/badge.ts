import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { DvIcon, type IconName } from '../icon/icon';

/** O tom de um selo: neutro ou um dos tons de status. */
export type BadgeTone = 'neutral' | 'ok' | 'warn' | 'info' | 'danger';

/**
 * Selo de estado curto ("Ao vivo", "já agiu", "fora de combate"): texto sempre presente, com ícone opcional e tom. A
 * informação nunca vai só na cor. `pending` troca o ícone por um ponto que pulsa enquanto o estado não se resolve
 * (movimento reduzido: o ponto fica parado).
 */
@Component({
  selector: 'dv-badge',
  imports: [DvIcon],
  template: `
    @if (pending()) {
      <span class="badge__dot" aria-hidden="true"></span>
    } @else if (icon(); as name) {
      <dv-icon [name]="name" size="sm" />
    }
    <ng-content />
  `,
  styleUrl: './badge.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '[class]': "'badge badge--' + tone()" },
})
export class DvBadge {
  readonly tone = input<BadgeTone>('neutral');
  readonly icon = input<IconName | null>(null);
  readonly pending = input(false);
}
