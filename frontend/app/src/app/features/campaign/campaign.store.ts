import { DestroyRef, Injectable, computed, effect, inject, signal, untracked } from '@angular/core';
import { Router } from '@angular/router';
import type { EditorTable } from '@contract/api_responses';
import { CampaignCatalog } from '@core/catalog/campaign-catalog';
import { SessionStore, type StoredTable } from '@core/session/session-store';
import { ServerTables } from '@core/tables/server-tables';
import { TableActionRunner } from '@core/tables/table-action-runner';
import { ASSUME_HOST_CONFIRM, CLOSE_TABLE_CONFIRM } from '@shared/game/server-tables';
import { ConfirmSheet } from '@shared/ui/confirm/confirm-sheet';
import { Sheet } from '@shared/ui/sheet/sheet';

/** Por quanto tempo "Esquecer" ainda pode ser desfeito. */
const UNDO_MS = 8000;

/** Uma mesa guardada neste aparelho, com o id dela. */
export type SavedTable = StoredTable & { tableId: string };

/**
 * O que as páginas de uma campanha sabem: a campanha, as mesas dela (as que o servidor conhece, quando este aparelho o
 * enxerga, e as guardadas neste navegador), esquecer uma (com desfazer por alguns segundos),
 * encerrá-la ou assumir o lugar de anfitrião de uma que este navegador não conhece. Quem fornece é a página; `campaignId` vem da rota.
 */
@Injectable()
export class CampaignStore {
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

  private readonly tableActions = new TableActionRunner();
  /** O que deu errado ao encerrar uma mesa ou assumir o lugar de anfitrião. */
  readonly serverError = this.tableActions.error;
  /** A mesa que está sendo encerrada ou assumida agora (bloqueia os botões das mesas até acabar). */
  readonly serverBusy = this.tableActions.busy;

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
  async close(tableId: string): Promise<boolean> {
    const ok = await this.sheet.open<boolean>(ConfirmSheet, {
      label: 'Encerrar a mesa',
      data: CLOSE_TABLE_CONFIRM,
    });
    return (
      ok === true &&
      this.tableActions.run(tableId, async () => {
        await this.serverTables.close(tableId);
        await this.loadServer();
      })
    );
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
    if (ok === true) {
      await this.tableActions.run(tableId, async () => {
        await this.serverTables.assumeHost(tableId, { id: campaign.id, title: campaign.title });
        await this.router.navigate(['/mesa', tableId]);
      });
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
