import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import type { ArchivedLog, ArchivedTable, EditorTable } from '@contract/api_responses';
import { ApiClient } from '../api/api-client';
import { SessionStore } from '../session/session-store';

/** A campanha a que uma mesa pertence: o suficiente para o navegador voltar a reconhecê-la. */
export interface TableCampaign {
  id: string;
  title: string;
}

/**
 * As mesas como o **servidor** as conhece. O navegador só guarda o token de quem entrou; quem manda na lista de mesas
 * é o servidor, e o que ele mostra vale em qualquer navegador desta máquina. Só a máquina do servidor alcança
 * essas rotas: de fora, ou com `--sem-editor`, a lista vem `null` e as telas voltam a confiar só no navegador.
 */
@Injectable({ providedIn: 'root' })
export class ServerTables {
  private readonly api = inject(ApiClient);
  private readonly session = inject(SessionStore);

  /** As mesas da campanha neste servidor, ou `null` se este aparelho não enxerga o servidor assim. */
  async list(campaignId: string): Promise<EditorTable[] | null> {
    try {
      return await firstValueFrom(this.api.editorTables(campaignId));
    } catch {
      return null;
    }
  }

  /** As mesas arquivadas da campanha, ou `null` se este aparelho não enxerga o servidor assim. */
  async listArchived(campaignId: string): Promise<ArchivedTable[] | null> {
    try {
      return await firstValueFrom(this.api.editorArchivedTables(campaignId));
    } catch {
      return null;
    }
  }

  /** Arquiva a mesa no servidor e a esquece neste navegador. A falha sobe, para a tela dizer o que houve. */
  async archive(tableId: string): Promise<void> {
    await firstValueFrom(this.api.editorArchiveTable(tableId));
    this.session.forget(tableId);
  }

  /** Restaura uma mesa arquivada. A falha sobe (campanha mudou, servidor cheio), para a tela dizer o que houve. */
  async restore(tableId: string): Promise<void> {
    await firstValueFrom(this.api.editorRestoreTable(tableId));
  }

  /** Apaga de vez uma mesa arquivada. A falha sobe. */
  async purge(tableId: string): Promise<void> {
    await firstValueFrom(this.api.editorPurgeTable(tableId));
  }

  /** O histórico de uma mesa arquivada. A falha sobe. */
  history(tableId: string): Promise<ArchivedLog> {
    return firstValueFrom(this.api.editorTableHistory(tableId));
  }

  /** Reemite o acesso do anfitrião e guarda o token novo neste navegador, que passa a conhecer a mesa. */
  async assumeHost(tableId: string, campaign: TableCampaign): Promise<void> {
    const access = await firstValueFrom(this.api.editorHostAccess(tableId));
    this.session.save(tableId, {
      token: access.token,
      playerId: access.player_id,
      role: 'host',
      title: campaign.title,
      campaignId: campaign.id,
      invite: access.invite_code,
      savedAt: Date.now(),
    });
  }
}
