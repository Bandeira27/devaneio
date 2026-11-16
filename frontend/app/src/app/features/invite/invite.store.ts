import { Injectable, computed, inject, signal } from '@angular/core';
import { SessionStore } from '@core/session/session-store';
import { inviteLink, isLocalOrigin, normalizeOrigin } from '@shared/game/invite';

/** O convite do anfitrião: o código guardado ao criar a mesa e o endereço que os outros aparelhos alcançam. */
@Injectable()
export class InviteStore {
  private readonly session = inject(SessionStore);

  readonly tableId = signal('');
  readonly addressText = signal(globalThis.location.origin);

  readonly entry = computed(() => this.session.get(this.tableId()));
  readonly code = computed(() => this.entry()?.invite ?? null);
  readonly isHost = computed(() => this.entry()?.role === 'host' && this.code() !== null);
  readonly origin = computed(() => normalizeOrigin(this.addressText()));
  readonly addressError = computed(() =>
    this.origin() === null ? 'Escreva um endereço como 192.168.0.5:8765.' : '',
  );
  readonly localWarning = computed(() => {
    const origin = this.origin();
    return origin !== null && isLocalOrigin(origin);
  });
  readonly link = computed(() => {
    const origin = this.origin();
    const code = this.code();
    return origin !== null && code !== null ? inviteLink(origin, this.tableId(), code) : '';
  });
}
