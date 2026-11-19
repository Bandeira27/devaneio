import { DestroyRef, Injectable, computed, effect, inject, signal, untracked } from '@angular/core';
import { Router } from '@angular/router';
import type { ArchivedTable, EditorTable } from '@contract/api_responses';
import { CampaignCatalog } from '@core/catalog/campaign-catalog';
import { SessionStore, type StoredTable } from '@core/session/session-store';
import { ServerTables } from '@core/tables/server-tables';
import { TableActionRunner } from '@core/tables/table-action-runner';
import {
  ARCHIVE_TABLE_CONFIRM,
  ASSUME_HOST_CONFIRM,
  archivedLine,
  purgeConfirm,
} from '@shared/game/server-tables';
import { ConfirmSheet } from '@shared/ui/confirm/confirm-sheet';
import { Sheet } from '@shared/ui/sheet/sheet';
import { HistorySheet } from './components/history-sheet/history-sheet';

/** Por quanto tempo "Esquecer" ainda pode ser desfeito. */
const UNDO_MS = 8000;

/** Uma mesa guardada neste aparelho, com o id dela. */
export type SavedTable = StoredTable & { tableId: string };

/**
 * O que as páginas de uma campanha sabem: a campanha, as mesas dela (as que o servidor conhece, quando este aparelho o
 * enxerga, e as guardadas neste navegador), esquecer uma (com desfazer por alguns segundos),
 * arquivá-la (e restaurá-la, ver o histórico ou apagá-la de vez) ou assumir o lugar de anfitrião de uma que este navegador não conhece. Quem fornece é a página; `campaignId` vem da rota.
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

  /** As mesas arquivadas desta campanha no servidor (vazia até a resposta ou se este aparelho não o enxerga). */
  readonly archivedList = signal<ArchivedTable[]>([]);

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

  /** As mesas que o servidor tem e este navegador não conhece (sem o token, não dá para abri-las: só assumir ou arquivar). */
  readonly serverOnly = computed<EditorTable[]>(() => {
    const known = new Set(this.session.list().map((table) => table.tableId));
    return (this.serverList() ?? []).filter((table) => !known.has(table.table_id));
  });

  private readonly tableActions = new TableActionRunner();
  /** O que deu errado ao arquivar, restaurar ou apagar uma mesa, ou ao assumir o lugar de anfitrião. */
  readonly serverError = this.tableActions.error;
  /** A mesa que está sendo arquivada, restaurada, apagada ou assumida agora (bloqueia os botões das mesas até acabar). */
  readonly serverBusy = this.tableActions.busy;

  /** O que acabou de dar certo (arquivar, restaurar, apagar), para a tela avisar; some na próxima ação. */
  readonly done = signal('');

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
    const [list, archived] = await Promise.all([
      this.serverTables.list(id),
      this.serverTables.listArchived(id),
    ]);
    if (this.campaignId() === id) {
      this.serverList.set(list);
      this.archivedList.set(archived ?? []);
    }
  }

  /** Arquiva uma mesa no servidor (depois de confirmar): sai do jogo para todos, mas o histórico fica e dá para restaurá-la. */
  async archive(tableId: string): Promise<boolean> {
    const ok = await this.sheet.open<boolean>(ConfirmSheet, {
      label: 'Arquivar a mesa',
      data: ARCHIVE_TABLE_CONFIRM,
    });
    return (
      ok === true &&
      this.tableActions.run(tableId, async () => {
        this.done.set('');
        await this.serverTables.archive(tableId);
        await this.loadServer();
        this.done.set(
          'Mesa arquivada. Ela está em “Mesas arquivadas”, de onde dá para restaurá-la.',
        );
      })
    );
  }

  /** Restaura uma mesa arquivada: volta para a lista e os acessos de antes voltam a valer. */
  restoreArchived(tableId: string): Promise<boolean> {
    return this.tableActions.run(tableId, async () => {
      this.done.set('');
      await this.serverTables.restore(tableId);
      await this.loadServer();
      this.done.set('Mesa restaurada. Ela voltou para a lista de mesas.');
    });
  }

  /** Apaga de vez uma mesa arquivada, com o histórico (depois de confirmar). */
  async purge(table: ArchivedTable): Promise<boolean> {
    const ok = await this.sheet.open<boolean>(ConfirmSheet, {
      label: 'Apagar a mesa de vez',
      data: purgeConfirm(archivedLine(table, Date.now())),
    });
    return (
      ok === true &&
      this.tableActions.run(table.table_id, async () => {
        this.done.set('');
        await this.serverTables.purge(table.table_id);
        await this.loadServer();
        this.done.set('Mesa apagada de vez.');
      })
    );
  }

  /** Abre o histórico (o log) de uma mesa arquivada. */
  async showHistory(table: ArchivedTable): Promise<void> {
    const host = table.host_name === '' ? 'mesa' : `mesa de ${table.host_name}`;
    await this.sheet.open<boolean>(HistorySheet, {
      label: 'Histórico da mesa',
      data: { tableId: table.table_id, title: host },
    });
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
