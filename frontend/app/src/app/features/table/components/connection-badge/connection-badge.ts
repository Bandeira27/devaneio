import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import type { LiveStatus } from '@core/live/live-feed';

const TEXT: Record<LiveStatus, string> = {
  connecting: 'Conectando…',
  live: 'Ao vivo',
  offline: 'Sem conexão. Tentando de novo…',
  expired: 'Sua sessão expirou.',
  gone: 'Esta mesa não existe mais.',
  failed: 'Algo deu errado.',
};

/** O estado da conexão com a mesa, em texto (nunca só cor). */
@Component({
  selector: 'dv-connection-badge',
  template: `<span class="dot" aria-hidden="true"></span>{{ text() }}`,
  styleUrl: './connection-badge.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { role: 'status', '[class]': "'badge badge--' + status()" },
})
export class ConnectionBadge {
  readonly status = input.required<LiveStatus>();
  protected readonly text = computed(() => TEXT[this.status()]);
}
