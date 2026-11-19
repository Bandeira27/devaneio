import { Injectable, computed, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import type { CampaignSummary } from '@contract/api_responses';
import { ApiClient } from '@core/api/api-client';
import { messageOf } from '@core/api/api-failure';

/** A leitura do catálogo: pedindo, pronta ou falhou. */
export type CatalogState = 'loading' | 'ready' | 'failed';

/**
 * As campanhas que o servidor oferece e se o editor atende este navegador (só o da máquina do servidor): a lista de cards da tela inicial e a
 * barra lateral de uma campanha leem daqui, para não perguntar duas vezes. `load` sempre pergunta de novo (a tela
 * inicial o chama a cada visita, e o editor, depois de gravar); `ensure` só pergunta se ainda não há resposta.
 */
@Injectable({ providedIn: 'root' })
export class CampaignCatalog {
  private readonly api = inject(ApiClient);
  private pending: Promise<void> | null = null;
  private queued: Promise<void> | null = null;

  readonly campaigns = signal<CampaignSummary[]>([]);
  readonly state = signal<CatalogState>('loading');
  readonly loadError = signal('');
  /** O editor de campanhas atende este navegador? Sem ele, nada oferece o roteiro. */
  readonly editorAvailable = signal(false);
  readonly ready = computed(() => this.state() === 'ready');
  /** Há uma pergunta ao servidor em andamento (a lista pode estar prestes a mudar). */
  readonly busy = signal(false);

  /** A campanha com esse id, ou `null` se o servidor não a conhece (ainda não gravada, ou apagada). */
  find(id: string): CampaignSummary | null {
    return this.campaigns().find((campaign) => campaign.id === id) ?? null;
  }

  /** Pergunta ao servidor só se ainda não houver resposta (ou se a última falhou). */
  ensure(): Promise<void> {
    return this.state() === 'ready' ? Promise.resolve() : this.load();
  }

  /**
   * Pergunta ao servidor. Se já há uma pergunta em andamento, ela pode ter sido feita antes do que o chamador acabou de
   * gravar: então vem uma nova logo depois dela, e as chamadas que chegam nesse meio-tempo dividem essa segunda.
   */
  load(): Promise<void> {
    if (this.pending === null) {
      this.pending = this.fetch();
    } else {
      this.queued ??= this.pending.then(() => {
        this.queued = null;
        return this.fetch();
      });
      this.pending = this.queued;
    }
    const mine = this.pending;
    void mine.finally(() => {
      if (this.pending === mine) {
        this.pending = null;
      }
    });
    return mine;
  }

  private async fetch(): Promise<void> {
    this.busy.set(true);
    void this.probeEditor();
    if (this.state() !== 'ready') {
      this.state.set('loading');
    }
    this.loadError.set('');
    try {
      this.campaigns.set(await firstValueFrom(this.api.campaigns()));
      this.state.set('ready');
    } catch (error) {
      this.loadError.set(messageOf(error));
      this.state.set('failed');
    } finally {
      this.busy.set(false);
    }
  }

  private async probeEditor(): Promise<void> {
    try {
      await firstValueFrom(this.api.editorCampaigns());
      this.editorAvailable.set(true);
    } catch {
      this.editorAvailable.set(false); // 404 com `--sem-editor` ou de fora da máquina do servidor, ou o servidor fora do ar: ninguém oferece o roteiro
    }
  }
}
