import { DestroyRef, Injectable, computed, effect, inject, signal, untracked } from '@angular/core';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import type { EditorTable } from '@contract/api_responses';
import { ApiClient } from '@core/api/api-client';
import { messageOf } from '@core/api/api-failure';
import { CampaignCatalog } from '@core/catalog/campaign-catalog';
import { SessionStore, type StoredTable } from '@core/session/session-store';
import { ServerTables } from '@core/tables/server-tables';
import { normalizeName, validateName } from '@shared/game/names';
import { ASSUME_HOST_CONFIRM, CLOSE_TABLE_CONFIRM } from '@shared/game/server-tables';
import { ConfirmSheet } from '@shared/ui/confirm/confirm-sheet';
import { Sheet } from '@shared/ui/sheet/sheet';

/** Por quanto tempo "Esquecer" ainda pode ser desfeito. */
const UNDO_MS = 8000;

/** Uma mesa guardada neste aparelho, com o id dela. */
export type SavedTable = StoredTable & { tableId: string };

/**
 * O que as páginas de uma campanha sabem: a campanha, as mesas dela (as que o servidor conhece, quando este aparelho o
 * enxerga, e as guardadas neste navegador), criar uma mesa nova, esquecer uma (com desfazer por alguns segundos),
 * encerrá-la ou assumir o lugar de anfitrião de uma que este navegador não conhece. Quem fornece é a página; `campaignId` vem da rota.
 */
@Injectable()
export class CampaignStore {
  private readonly api = inject(ApiClient);
  private readonly session = inject(SessionStore);
  private readonly router = inject(Router);
  private readonly catalog = inject(CampaignCatalog);
  private readonly serverTables = inject(ServerTables);
  private readonly sheet = inject(Sheet);

  readonly campaignId = signal('');
  readonly campaign = computed(() => this.catalog.find(this.campaignId()));

  /**
   * As mesas desta campanha **no servidor**; `null` até a resposta, ou se este aparelho não enxerga o servidor assim (de
   * fora da máquina dele, ou sem o editor). Com a lista, quem manda é o servidor; sem ela, só o navegador.
   */
  readonly serverList = signal<EditorTable[] | null>(null);

  /**
   * As mesas que este navegador conhece, da mais recente para a mais antiga. As guardadas antes de o app anotar a campanha
   * só têm o título e casam por ele até serem abertas de novo. Com a lista do servidor, some a que o servidor não tem mais.
   */
  readonly tables = computed<SavedTable[]>(() => {
    const id = this.campaignId();
    const title = this.campaign()?.title;
    const onServer = this.serverList()?.map((table) => table.table_id);
    return this.session
      .list()
      .filter(
        (table) =>
          table.campaignId === id || (table.campaignId === undefined && table.title === title),
      )
      .filter((table) => onServer === undefined || onServer.includes(table.tableId));
  });

  /** As mesas que o servidor tem e este navegador não conhece (sem o token, não dá para abri-las: só assumir ou encerrar). */
  readonly serverOnly = computed<EditorTable[]>(() => {
    const known = new Set(this.session.list().map((table) => table.tableId));
    return (this.serverList() ?? []).filter((table) => !known.has(table.table_id));
  });

  /** O que deu errado ao encerrar uma mesa ou assumir o lugar de anfitrião. */
  readonly serverError = signal('');

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
    effect(() => {
      const id = this.campaignId();
      untracked(() => void this.loadServer(id));
    });
  }

  /** Pergunta ao servidor quais mesas a campanha tem. A resposta de uma campanha que já mudou é ignorada. */
  async loadServer(id = this.campaignId()): Promise<void> {
    if (id === '') {
      return;
    }
    const list = await this.serverTables.list(id);
    if (this.campaignId() === id) {
      this.serverList.set(list);
    }
  }

  /** Encerra uma mesa no servidor (depois de confirmar): some para todos os navegadores. */
  async close(tableId: string): Promise<void> {
    const ok = await this.sheet.open<boolean>(ConfirmSheet, {
      label: 'Encerrar a mesa',
      data: CLOSE_TABLE_CONFIRM,
    });
    if (ok !== true) {
      return;
    }
    this.serverError.set('');
    try {
      await this.serverTables.close(tableId);
      await this.loadServer();
    } catch (error) {
      this.serverError.set(messageOf(error));
    }
  }

  /** Assume o lugar de anfitrião de uma mesa que este navegador não conhece (depois de confirmar) e vai para ela. */
  async assume(tableId: string): Promise<void> {
    const campaign = this.campaign();
    if (campaign === null) {
      return;
    }
    const ok = await this.sheet.open<boolean>(ConfirmSheet, {
      label: 'Assumir como anfitrião',
      data: ASSUME_HOST_CONFIRM,
    });
    if (ok !== true) {
      return;
    }
    this.serverError.set('');
    try {
      await this.serverTables.assumeHost(tableId, { id: campaign.id, title: campaign.title });
      await this.router.navigate(['/mesa', tableId]);
    } catch (error) {
      this.serverError.set(messageOf(error));
    }
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
      // A mesa nasce numa sala de espera: o anfitrião cai nela, convida e cria o personagem por lá.
      await this.router.navigate(['/mesa', created.table_id]);
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
