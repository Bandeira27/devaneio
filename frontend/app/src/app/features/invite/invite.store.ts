import { Injectable, computed, inject, signal } from '@angular/core';
import { SessionStore } from '@core/session/session-store';
import { describeInvite } from '@shared/game/invite';

/** O convite do anfitrião: o código guardado ao criar a mesa e o endereço que os outros aparelhos alcançam. */
@Injectable()
export class InviteStore {
  private readonly session = inject(SessionStore);

  readonly tableId = signal('');
  readonly addressText = signal(globalThis.location.origin);

  readonly entry = computed(() => this.session.get(this.tableId()));
  readonly code = computed(() => this.entry()?.invite ?? null);
  private readonly invite = computed(() =>
    describeInvite(this.addressText(), this.tableId(), this.code()),
  );
  readonly addressError = computed(() => this.invite().error);
  readonly localWarning = computed(() => this.invite().localWarning);
  readonly link = computed(() => this.invite().link);
}
