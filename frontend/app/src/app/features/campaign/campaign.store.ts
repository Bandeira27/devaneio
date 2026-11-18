import { DestroyRef, Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ApiClient } from '@core/api/api-client';
import { messageOf } from '@core/api/api-failure';
import { CampaignCatalog } from '@core/catalog/campaign-catalog';
import { SessionStore, type StoredTable } from '@core/session/session-store';
import { normalizeName, validateName } from '@shared/game/names';

/** Por quanto tempo "Esquecer" ainda pode ser desfeito. */
const UNDO_MS = 8000;

/** Uma mesa guardada neste aparelho, com o id dela. */
export type SavedTable = StoredTable & { tableId: string };

/**
 * O que as páginas de uma campanha sabem: a campanha, as mesas dela guardadas neste aparelho, criar uma mesa nova e
 * esquecer uma (com desfazer por alguns segundos). Quem fornece é a página; `campaignId` vem da rota.
 */
@Injectable()
export class CampaignStore {
  private readonly api = inject(ApiClient);
  private readonly session = inject(SessionStore);
  private readonly router = inject(Router);
  private readonly catalog = inject(CampaignCatalog);

  readonly campaignId = signal('');
  readonly campaign = computed(() => this.catalog.find(this.campaignId()));

  /**
   * As mesas desta campanha, da mais recente para a mais antiga. As guardadas antes de o app anotar a campanha só têm o
   * título e casam por ele até serem abertas de novo.
   */
  readonly tables = computed<SavedTable[]>(() => {
    const id = this.campaignId();
    const title = this.campaign()?.title;
    return this.session
      .list()
      .filter(
        (table) =>
          table.campaignId === id || (table.campaignId === undefined && table.title === title),
      );
  });

  readonly hostName = signal('');
  readonly nameError = signal('');
  readonly creating = signal(false);
  readonly createError = signal('');

  /** A mesa que acabou de ser esquecida, para desfazer por alguns segundos. */
  readonly forgotten = signal<{ tableId: string; title: string } | null>(null);
  private undo: { tableId: string; entry: StoredTable } | null = null;
  private undoTimer: ReturnType<typeof setTimeout> | undefined;

  constructor() {
    inject(DestroyRef).onDestroy(() => clearTimeout(this.undoTimer));
  }

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
      await this.router.navigate(['/mesa', created.table_id, 'personagem']);
    } catch (error) {
      this.createError.set(messageOf(error));
    } finally {
      this.creating.set(false);
    }
  }

  /** Esquece a mesa, mas guarda a entrada por alguns segundos: o token e o convite voltam se a pessoa desfizer. */
  forget(tableId: string): void {
    const entry = this.session.get(tableId);
    if (entry === null) {
      return;
    }
    this.settleForget(); // um segundo "Esquecer" encerra o desfazer do primeiro: o aviso é um só
    this.session.forget(tableId);
    this.undo = { tableId, entry };
    this.forgotten.set({ tableId, title: entry.title });
    this.undoTimer = setTimeout(() => this.settleForget(), UNDO_MS);
  }

  restore(): void {
    if (this.undo !== null) {
      this.session.save(this.undo.tableId, this.undo.entry);
    }
    this.settleForget();
  }

  private settleForget(): void {
    clearTimeout(this.undoTimer);
    this.undo = null;
    this.forgotten.set(null);
  }
}
