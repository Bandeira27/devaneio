import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import type { LiveStatus } from '@core/live/live-feed';
import { DvBadge, type BadgeTone } from '@shared/ui/badge/badge';
import type { IconName } from '@shared/ui/icon/icon';

const VIEW: Record<LiveStatus, { text: string; tone: BadgeTone; icon: IconName | null }> = {
  connecting: { text: 'Conectando…', tone: 'info', icon: null },
  live: { text: 'Ao vivo', tone: 'ok', icon: 'ok' },
  offline: { text: 'Sem conexão', tone: 'warn', icon: 'warn' },
  expired: { text: 'Sessão expirada', tone: 'danger', icon: 'danger' },
  gone: { text: 'Mesa não encontrada', tone: 'danger', icon: 'danger' },
  failed: { text: 'Algo deu errado', tone: 'danger', icon: 'danger' },
};

/**
 * O estado da conexão com a mesa: selo com texto e ícone (nunca só cor); só "conectando" pulsa. O texto é um rótulo
 * curto (o selo vai em caixa-alta); a explicação e o que fazer ficam no aviso da mesa.
 */
@Component({
  selector: 'dv-connection-badge',
  imports: [DvBadge],
  templateUrl: './connection-badge.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { role: 'status' },
})
export class ConnectionBadge {
  readonly status = input.required<LiveStatus>();
  protected readonly view = computed(() => VIEW[this.status()]);
}
