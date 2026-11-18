import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import type { CampaignSummary } from '@contract/api_responses';
import { CampaignCatalog } from '@core/catalog/campaign-catalog';
import { SessionStore } from '@core/session/session-store';
import { parseInvite } from '@shared/game/invite';

/** Uma campanha da lista, com as mesas dela neste aparelho. */
export interface CampaignCard extends CampaignSummary {
  /** Quantas mesas desta campanha estão guardadas neste aparelho. */
  tables: number;
}

/** Estado da tela inicial: as campanhas em cards, a mesa mais recente para continuar e entrar por link de convite. */
@Injectable()
export class HomeStore {
  private readonly catalog = inject(CampaignCatalog);
  private readonly session = inject(SessionStore);
  private readonly router = inject(Router);

  readonly state = this.catalog.state;
  readonly loadError = this.catalog.loadError;
  /** O servidor tem o editor de campanhas ligado (`--editor`)? Sem ele, a lista não oferece "Nova campanha". */
  readonly editorAvailable = this.catalog.editorAvailable;

  /** As campanhas, cada uma com quantas mesas guardadas tem. As mesas antigas (sem o id) casam pelo título. */
  readonly cards = computed<CampaignCard[]>(() => {
    const saved = this.session.list();
    return this.catalog.campaigns().map((campaign) => ({
      ...campaign,
      tables: saved.filter(
        (table) =>
          table.campaignId === campaign.id ||
          (table.campaignId === undefined && table.title === campaign.title),
      ).length,
    }));
  });

  /** A mesa guardada mais recente, para "Continuar de onde parou". */
  readonly latest = computed(() => this.session.list()[0] ?? null);

  readonly inviteText = signal('');
  readonly inviteError = signal('');

  setInviteText(value: string): void {
    this.inviteText.set(value);
    this.inviteError.set('');
  }

  load(): Promise<void> {
    return this.catalog.load();
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
}
