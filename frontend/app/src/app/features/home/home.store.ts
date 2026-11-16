import { Injectable, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import type { CampaignSummary } from '@contract/api_responses';
import { ApiClient } from '@core/api/api-client';
import { messageOf } from '@core/api/api-failure';
import { SessionStore } from '@core/session/session-store';
import { normalizeName, validateName } from '@shared/game/commands';
import { parseInvite } from '@shared/game/invite';

export type LoadState = 'loading' | 'ready' | 'failed';

@Injectable()
export class HomeStore {
  private readonly api = inject(ApiClient);
  private readonly session = inject(SessionStore);
  private readonly router = inject(Router);

  readonly saved = this.session.list;
  readonly campaigns = signal<CampaignSummary[]>([]);
  readonly state = signal<LoadState>('loading');
  readonly loadError = signal('');

  readonly campaignId = signal('');
  readonly hostName = signal('');
  readonly nameError = signal('');
  readonly creating = signal(false);
  readonly createError = signal('');

  readonly inviteText = signal('');
  readonly inviteError = signal('');

  async load(): Promise<void> {
    this.state.set('loading');
    this.loadError.set('');
    try {
      const list = await firstValueFrom(this.api.campaigns());
      this.campaigns.set(list);
      this.campaignId.set(list[0]?.id ?? '');
      this.state.set('ready');
    } catch (error) {
      this.loadError.set(messageOf(error));
      this.state.set('failed');
    }
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
        invite: created.invite_code,
        savedAt: Date.now(),
      });
      await this.router.navigate(['/mesa', created.table_id, 'convite']);
    } catch (error) {
      this.createError.set(messageOf(error));
    } finally {
      this.creating.set(false);
    }
  }

  async openInvite(): Promise<void> {
    const invite = parseInvite(this.inviteText());
    if (invite === null) {
      this.inviteError.set('Isso não parece um link de convite.');
      return;
    }
    this.inviteError.set('');
    await this.router.navigate(['/entrar', invite.tableId, invite.code]);
  }

  forget(tableId: string): void {
    this.session.forget(tableId);
  }
}
