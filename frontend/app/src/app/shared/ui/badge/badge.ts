import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { DvIcon, type IconName } from '../icon/icon';

/** O tom de um selo: neutro ou um dos tons de status. */
export type BadgeTone = 'neutral' | 'ok' | 'warn' | 'info' | 'danger';

/**
 * Selo de estado curto ("Ao vivo", "já agiu", "fora de combate"): uma anotação, não um botão: sem caixa nem fundo, com
 * ícone opcional, texto em caixa-alta e um filete pontilhado; o tom só muda a cor. A informação nunca vai só na cor. `pending` troca o ícone por um ponto que pulsa enquanto o estado não se resolve
 * (movimento reduzido: o ponto fica parado).
 */
@Component({
  selector: 'dv-badge',
  imports: [DvIcon],
  templateUrl: './badge.html',
  styleUrl: './badge.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '[class]': "'badge badge--' + tone()" },
})
export class DvBadge {
  readonly tone = input<BadgeTone>('neutral');
  readonly icon = input<IconName | null>(null);
  readonly pending = input(false);
}
