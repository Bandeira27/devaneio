import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import type { BeatStatus } from '@contract/api_responses';
import { beat } from '@shared/game/commands';
import { beatStatusText } from '@shared/game/host';
import { DvBadge, type BadgeTone } from '@shared/ui/badge/badge';
import { DvButton } from '@shared/ui/button/button';
import { DvDisclosure } from '@shared/ui/disclosure/disclosure';
import type { IconName } from '@shared/ui/icon/icon';
import { TableStore } from '../table.store';

const TONES: Record<BeatStatus, { tone: BadgeTone; icon: IconName | null }> = {
  pending: { tone: 'neutral', icon: null },
  active: { tone: 'info', icon: 'info' },
  done: { tone: 'ok', icon: 'ok' },
  failed: { tone: 'danger', icon: 'danger' },
};

/**
 * Os marcos da trama com o estado de cada um e os botões que os movem à mão (`marco ativar|concluir|falhar`). O botão
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
  protected readonly tones = TONES;
  protected readonly statusText = beatStatusText;

  protected run(action: 'ativar' | 'concluir' | 'falhar', id: string): void {
    void this.store.run(beat(action, id));
  }
}
