import { DestroyRef, Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import type { CampaignSummary } from '@contract/api_responses';
import { ApiClient } from '@core/api/api-client';
import { messageOf } from '@core/api/api-failure';
import { SessionStore, type StoredTable } from '@core/session/session-store';
import { normalizeName, validateName } from '@shared/game/names';
import { parseInvite } from '@shared/game/invite';
import type { LoadState } from '@shared/game/load-state';

/** Por quanto tempo "Esquecer" ainda pode ser desfeito. */
const UNDO_MS = 8000;

/** Estado da tela inicial: campanhas, mesas guardadas, criar mesa e entrar por link. */
@Injectable()
export class HomeStore {
  private readonly api = inject(ApiClient);
  private readonly session = inject(SessionStore);
  private readonly router = inject(Router);

  readonly saved = this.session.list;
  readonly campaigns = signal<CampaignSummary[]>([]);
  readonly state = signal<LoadState>('loading');
  readonly loadError = signal('');
  /** O servidor tem o editor de campanhas ligado (`--editor`)? Sem ele, a home não oferece o link. */
  readonly editorAvailable = signal(false);

  readonly campaignId = signal('');
  /** A premissa da campanha escolhida: o que o jogador vai encontrar. */
  readonly premise = computed(
    () => this.campaigns().find((c) => c.id === this.campaignId())?.premise ?? '',
  );
  readonly hostName = signal('');
  readonly nameError = signal('');
  readonly creating = signal(false);
  readonly createError = signal('');

  readonly inviteText = signal('');
  readonly inviteError = signal('');

  setHostName(value: string): void {
    this.hostName.set(value);
    this.nameError.set('');
  }

  setInviteText(value: string): void {
    this.inviteText.set(value);
    this.inviteError.set('');
  }

  async load(): Promise<void> {
    void this.probeEditor();
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

  private async probeEditor(): Promise<void> {
    try {
      await firstValueFrom(this.api.editorCampaigns());
      this.editorAvailable.set(true);
    } catch {
      this.editorAvailable.set(false); // 404 sem `--editor`, ou o servidor fora do ar: a home segue sem o link
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
      await this.router.navigate(['/mesa', created.table_id, 'personagem']);
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

  /** A mesa que acabou de ser esquecida, para desfazer por alguns segundos. */
  readonly forgotten = signal<{ tableId: string; title: string } | null>(null);
  private undo: { tableId: string; entry: StoredTable } | null = null;
  private undoTimer: ReturnType<typeof setTimeout> | undefined;

  constructor() {
    inject(DestroyRef).onDestroy(() => clearTimeout(this.undoTimer));
  }

  /** Esquece a mesa, mas guarda a entrada por alguns segundos: o token e o convite voltam se a pessoa desfizer. */
  forget(tableId: string): void {
    const entry = this.session.get(tableId);
    if (entry === null) {
      return;
    }
    this.session.forget(tableId);
    this.undo = { tableId, entry };
    this.forgotten.set({ tableId, title: entry.title });
    clearTimeout(this.undoTimer);
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
