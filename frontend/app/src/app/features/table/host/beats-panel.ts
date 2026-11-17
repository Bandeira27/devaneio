import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import type { BeatStatus } from '@contract/api_responses';
import { beat, type BeatAction } from '@shared/game/commands';
import { beatStatusText } from '@shared/game/host';
import { DvBadge, type BadgeTone } from '@shared/ui/badge/badge';
import { DvButton } from '@shared/ui/button/button';
import { DvDisclosure } from '@shared/ui/disclosure/disclosure';
import { ConfirmSheet } from '@shared/ui/confirm/confirm-sheet';
import { Sheet } from '@shared/ui/sheet/sheet';
import type { IconName } from '@shared/ui/icon/icon';
import { TableStore } from '../table.store';

const TONES: Record<BeatStatus, { tone: BadgeTone; icon: IconName | null }> = {
  pending: { tone: 'neutral', icon: null },
  active: { tone: 'info', icon: 'info' },
  done: { tone: 'ok', icon: 'ok' },
  failed: { tone: 'danger', icon: 'danger' },
};

/**
 * Os marcos da trama com o estado de cada um e os botões que os movem à mão (`marco ativar|concluir|falhar`; concluir e falhar pedem confirmação). O botão
 * que não vale agora fica bloqueado com o motivo escrito logo abaixo, e quem decide é sempre o motor. As notas privadas
 * ficam recolhidas.
 */
@Component({
  selector: 'dv-beats-panel',
  imports: [DvBadge, DvButton, DvDisclosure],
  templateUrl: './beats-panel.html',
  styleUrl: './host-lists.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BeatsPanel {
  protected readonly store = inject(TableStore);
  private readonly sheet = inject(Sheet);
  protected readonly tones = TONES;
  protected readonly statusText = beatStatusText;

  /** Ativar vai direto; concluir e falhar mexem na trama toda e pedem confirmação. */
  protected async run(action: BeatAction, id: string, title: string): Promise<void> {
    if (action !== 'ativar') {
      const verb = action === 'concluir' ? 'Concluir' : 'Falhar';
      const ok = await this.sheet.open<boolean>(ConfirmSheet, {
        label: `${verb} o marco`,
        data: {
          title: `${verb} o marco`,
          text: `${verb} o marco "${title}": a trama segue a partir daí e os jogadores veem a mudança.`,
          action: verb,
        },
      });
      if (!ok) {
        return;
      }
    }
    await this.store.run(beat(action, id));
  }
}
