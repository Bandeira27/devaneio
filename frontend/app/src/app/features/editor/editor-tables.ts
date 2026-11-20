import { Injectable, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import type { EditorTable } from '@contract/api_responses';
import { ApiClient } from '@core/api/api-client';
import { SessionStore } from '@core/session/session-store';
import { ServerTables } from '@core/tables/server-tables';
import { TableActionRunner } from '@core/tables/table-action-runner';
import { ARCHIVE_TABLE_CONFIRM, ASSUME_HOST_CONFIRM } from '@shared/game/server-tables';
import { ConfirmSheet } from '@shared/ui/confirm/confirm-sheet';
import { Sheet } from '@shared/ui/sheet/sheet';

/**
 * As mesas do servidor que travam uma campanha no editor, e o que se faz com elas: arquivar (e liberar a campanha se era
 * a última) ou assumir o lugar de anfitrião. Não conhece a campanha em edição: quem chama diz o id e o título, e recebe
 * de volta o que mudou. Cada editor tem o seu (o erro e o "ocupado" de um não aparecem em outro).
 */
@Injectable()
export class EditorTables {
  private readonly api = inject(ApiClient);
  private readonly router = inject(Router);
  private readonly sheet = inject(Sheet);
  private readonly serverTables = inject(ServerTables);
  private readonly session = inject(SessionStore);
  private readonly actions = new TableActionRunner();

  /** As mesas que travam a campanha (só enquanto ela não pode ser regravada). */
  readonly list = signal<EditorTable[]>([]);
  /** O que deu errado ao arquivar uma mesa ou assumir o lugar de anfitrião. */
  readonly error = this.actions.error;
  /** A mesa que está sendo arquivada ou assumida agora (bloqueia os botões das mesas até acabar). */
  readonly busy = this.actions.busy;

  /** Relê as mesas que travam a campanha, ou esvazia a lista se ela é nova ou pode ser regravada. */
  async load(campaignId: string | null, writable: boolean): Promise<void> {
    this.list.set(
      campaignId !== null && !writable ? ((await this.serverTables.list(campaignId)) ?? []) : [],
    );
  }

  /** O navegador já tem o acesso a esta mesa (dá para abri-la sem assumir)? */
  knows(tableId: string): boolean {
    return this.session.get(tableId) !== null;
  }

  /**
   * Arquiva uma mesa (depois de confirmar). Devolve se a campanha já pode ser regravada, ou `null` se o autor desistiu ou
   * a ação falhou (o motivo fica em `error`).
   */
  async archive(tableId: string, campaignId: string | null): Promise<{ writable: boolean } | null> {
    const ok = await this.sheet.open<boolean>(ConfirmSheet, {
      label: 'Arquivar a mesa',
      data: ARCHIVE_TABLE_CONFIRM,
    });
    if (ok !== true) {
      return null;
    }
    let writable = true;
    const done = await this.actions.run(tableId, async () => {
      await this.serverTables.archive(tableId);
      const campaigns = await firstValueFrom(this.api.editorCampaigns());
      writable = campaigns.find((c) => c.id === campaignId)?.writable ?? true;
      await this.load(campaignId, writable);
    });
    return done ? { writable } : null;
  }

  /** Assume o lugar de anfitrião de uma mesa (depois de confirmar) e vai para ela. */
  async assumeHost(tableId: string, campaign: { id: string; title: string }): Promise<void> {
    const ok = await this.sheet.open<boolean>(ConfirmSheet, {
      label: 'Assumir como anfitrião',
      data: ASSUME_HOST_CONFIRM,
    });
    if (ok === true) {
      await this.actions.run(tableId, async () => {
        await this.serverTables.assumeHost(tableId, campaign);
        await this.router.navigate(['/mesa', tableId]);
      });
    }
  }
}
