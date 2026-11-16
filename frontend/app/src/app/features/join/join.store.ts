import { Injectable, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ApiClient } from '@core/api/api-client';
import { messageOf } from '@core/api/api-failure';
import { SessionStore } from '@core/session/session-store';
import { normalizeName, validateName } from '@shared/game/names';
import { isInviteCode } from '@shared/game/invite';

/** Estado da tela de entrar numa mesa pelo convite. */
@Injectable()
export class JoinStore {
  private readonly api = inject(ApiClient);
  private readonly session = inject(SessionStore);
  private readonly router = inject(Router);

  readonly tableId = signal('');
  readonly code = signal('');
  readonly name = signal('');
  readonly nameError = signal('');
  readonly codeError = signal('');
  readonly joining = signal(false);
  readonly error = signal('');

  /** Já entrou nesta mesa por este navegador: vai direto, sem pedir o convite de novo. */
  alreadyIn(): boolean {
    return this.session.get(this.tableId()) !== null;
  }

  async join(): Promise<void> {
    const name = normalizeName(this.name());
    const nameProblem = validateName(name, 'Escreva o seu nome.');
    const codeProblem = isInviteCode(this.code().trim()) ? '' : 'Cole o código do convite.';
    this.nameError.set(nameProblem ?? '');
    this.codeError.set(codeProblem);
    this.error.set('');
    if (nameProblem !== null || codeProblem !== '') {
      return;
    }
    this.joining.set(true);
    try {
      const tableId = this.tableId();
      const joined = await firstValueFrom(
        this.api.joinTable(tableId, { invite_code: this.code().trim(), name }),
      );
      this.session.save(tableId, {
        token: joined.token,
        playerId: joined.player_id,
        role: 'player',
        title: joined.table.campaign.title,
        savedAt: Date.now(),
      });
      await this.router.navigate(['/mesa', tableId, 'personagem']);
    } catch (error) {
      this.error.set(messageOf(error));
    } finally {
      this.joining.set(false);
    }
  }
}
