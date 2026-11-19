import { Injectable, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ApiClient } from '@core/api/api-client';
import { messageOf } from '@core/api/api-failure';
import { SessionStore } from '@core/session/session-store';
import { normalizeName, validateName } from '@shared/game/names';

/**
 * Criar uma mesa, o primeiro passo do caminho de entrada do anfitrião: pede o nome de quem vai ser o anfitrião, cria a
 * mesa, guarda a entrada neste navegador e segue para o personagem. Quem fornece é a página; `campaignId` vem da rota.
 */
@Injectable()
export class CreateTableStore {
  private readonly api = inject(ApiClient);
  private readonly session = inject(SessionStore);
  private readonly router = inject(Router);

  readonly campaignId = signal('');
  readonly hostName = signal('');
  readonly nameError = signal('');
  readonly creating = signal(false);
  readonly createError = signal('');

  setHostName(value: string): void {
    this.hostName.set(value);
    this.nameError.set('');
  }

  async create(): Promise<void> {
    const name = normalizeName(this.hostName());
    const problem = validateName(name, 'Escreva o seu nome.');
    this.nameError.set(problem ?? '');
    this.createError.set('');
    if (problem !== null || this.campaignId() === '') {
      return;
    }
    this.creating.set(true);
    try {
      const created = await firstValueFrom(
        this.api.createTable({ campaign_id: this.campaignId(), host_name: name }),
      );
      this.session.save(created.table_id, {
        token: created.host_token,
        playerId: created.table.you,
        role: 'host',
        title: created.table.campaign.title,
        campaignId: created.table.campaign.id,
        invite: created.invite_code,
        savedAt: Date.now(),
      });
      // O caminho de entrada segue: depois da mesa vem o personagem, e só então a sala de espera.
      await this.router.navigate(['/mesa', created.table_id, 'personagem']);
    } catch (error) {
      this.createError.set(messageOf(error));
    } finally {
      this.creating.set(false);
    }
  }
}
