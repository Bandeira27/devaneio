import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { campaignEmblem } from '@shared/game/emblem';
import { DvIcon } from '../icon/icon';

/**
 * O emblema de uma campanha: um ícone num círculo, no tom que o id da campanha escolhe (sempre o mesmo para o mesmo id).
 * Decorativo: o nome da campanha sempre vem junto, em texto, então fica fora do leitor de tela. O tamanho `lg` é o do
 * card da tela inicial; `md` o da barra lateral.
 */
@Component({
  selector: 'dv-emblem',
  imports: [DvIcon],
  template: `<dv-icon [name]="emblem().icon" />`,
  styleUrl: './emblem.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    'aria-hidden': 'true',
    '[class]': "'emblem emblem--' + emblem().tone + ' emblem--' + size()",
  },
})
export class DvEmblem {
  /** O id da campanha. */
  readonly campaignId = input.required<string>();
  readonly size = input<'md' | 'lg'>('md');
  protected readonly emblem = computed(() => campaignEmblem(this.campaignId()));
}
