import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { DvBadge } from '@shared/ui/badge/badge';
import { DvDisclosure } from '@shared/ui/disclosure/disclosure';
import { DvPips } from '@shared/ui/pips/pips';
import { TableStore } from '../table.store';

/**
 * Os NPCs (onde estão, vida, se caíram, disposição e notas privadas) e os locais (descrição e notas privadas, o atual
 * primeiro). Só leitura: para mudar algo, as ferramentas do turno e os comandos.
 */
@Component({
  selector: 'dv-world-panel',
  imports: [DvBadge, DvDisclosure, DvPips],
  templateUrl: './world-panel.html',
  styleUrl: './host-lists.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class WorldPanel {
  protected readonly store = inject(TableStore);
}
