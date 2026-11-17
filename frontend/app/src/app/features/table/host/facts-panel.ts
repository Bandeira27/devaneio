import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { reveal } from '@shared/game/commands';
import { DvBadge } from '@shared/ui/badge/badge';
import { DvButton } from '@shared/ui/button/button';
import { TableStore } from '../table.store';

/**
 * Os fatos da campanha. O oculto aparece em "tinta borrada" (clareia em hover, foco e toque) e sempre com o selo
 * "Oculto": o estado nunca vai só no borrão, e o leitor de tela lê o texto normalmente. `Revelar` torna o fato público
 * pelo motor; o selo do revelado entra com a animação de entrada, porque o anfitrião precisa notar a mudança.
 */
@Component({
  selector: 'dv-facts-panel',
  imports: [DvBadge, DvButton],
  templateUrl: './facts-panel.html',
  styleUrl: './host-lists.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FactsPanel {
  protected readonly store = inject(TableStore);

  protected reveal(id: string): void {
    void this.store.run(reveal(id));
  }
}
