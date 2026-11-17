import { Injectable, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ApiClient } from '@core/api/api-client';
import { ApiFailure, messageOf } from '@core/api/api-failure';
import { SessionStore } from '@core/session/session-store';
import { normalizeName, validateName } from '@shared/game/names';
import { isInviteCode } from '@shared/game/invite';

/** O que a tela sabe da mesa a que o convite leva. */
export type InvitePreviewState =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'ready'; title: string }
  | { kind: 'invalid'; message: string }
  | { kind: 'unavailable' };

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
  /** Para onde o convite leva (o nome da mesa), perguntado uma vez ao abrir o link; falha de rede não bloqueia a entrada. */
  readonly preview = signal<InvitePreviewState>({ kind: 'idle' });

  /**
   * Pergunta ao servidor o nome da mesa do convite. Só quando o código tem o formato certo e uma vez por abertura da tela
   * (nunca a cada tecla: cada tentativa errada custa uma leitura da mesa no servidor). Convite recusado (401) vira
   * `invalid`; qualquer outra falha vira `unavailable` e a tela segue com o texto genérico.
   */
  async loadPreview(): Promise<void> {
    const code = this.code().trim();
    if (!isInviteCode(code)) {
      return;
    }
    this.preview.set({ kind: 'loading' });
    try {
      const { title } = await firstValueFrom(
        this.api.invitePreview(this.tableId(), { invite_code: code }),
      );
      this.preview.set({ kind: 'ready', title });
    } catch (error) {
      this.preview.set(
        error instanceof ApiFailure && error.status === 401
          ? { kind: 'invalid', message: messageOf(error) }
          : { kind: 'unavailable' },
      );
    }
  }

  setName(value: string): void {
    this.name.set(value);
    this.nameError.set('');
    this.error.set('');
  }

  setCode(value: string): void {
    this.code.set(value);
    this.codeError.set('');
    this.error.set('');
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
