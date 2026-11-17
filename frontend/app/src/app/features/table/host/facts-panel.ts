import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Injector,
  afterNextRender,
  inject,
} from '@angular/core';
import { reveal } from '@shared/game/commands';
import { DvBadge } from '@shared/ui/badge/badge';
import { DvButton } from '@shared/ui/button/button';
import { focusElement } from '@shared/ui/focus';
import { Sheet } from '@shared/ui/sheet/sheet';
import { TableStore } from '../table.store';
import { ConfirmSheet } from './sheets/confirm-sheet';

const LABEL_MAX = 50;

/**
 * Os fatos da campanha. O oculto aparece em "tinta borrada" (clareia em hover e foco) e sempre com o selo "Oculto",
 * que vem antes do texto: o estado nunca vai só no borrão. `Revelar` torna o fato público para o grupo todo, então
 * pede confirmação; depois o foco vai para o texto do fato (o botão some) e o selo do revelado entra com a animação de
 * entrada, porque o anfitrião precisa notar a mudança.
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
  private readonly sheet = inject(Sheet);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly injector = inject(Injector);

  /** O nome do botão: o verbo e o começo do fato, para quem ouve a lista de botões saber qual é. */
  protected labelOf(text: string): string {
    return `Revelar: ${text.length > LABEL_MAX ? `${text.slice(0, LABEL_MAX)}…` : text}`;
  }

  protected async reveal(id: string, text: string): Promise<void> {
    const ok = await this.sheet.open<boolean>(ConfirmSheet, {
      label: 'Revelar o fato',
      data: {
        title: 'Revelar o fato',
        text: `Todos os jogadores passam a ver: "${text}". Isso não tem volta.`,
        action: 'Revelar',
      },
    });
    if (ok && (await this.store.run(reveal(id)))) {
      afterNextRender(
        () => {
          const el = this.host.nativeElement.querySelector<HTMLElement>(`[data-fact="${id}"]`);
          if (el) {
            focusElement(el);
          }
        },
        { injector: this.injector },
      );
    }
  }
}
