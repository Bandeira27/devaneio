import { Injectable, computed, inject, signal } from '@angular/core';
import { ApiFailure } from '../api/api-failure';
import { StoredTable, TABLE_ID } from './session-entry';
import { SESSION_STORAGE, readTables, writeTables } from './session-storage';

export type { StoredRole, StoredTable } from './session-entry';
export { SESSION_STORAGE, STORAGE_KEY } from './session-storage';

export const MAX_TABLES = 20;

/**
 * As mesas em que este navegador entrou (token, `player_id`, papel). O token só viaja no cabeçalho
 * `Authorization`; fica no `localStorage`, que um XSS leria (risco aceito, rule 05 item 24). Tudo que
 * volta do armazenamento é validado, e sem armazenamento a sessão vive só na memória da aba.
 */
@Injectable({ providedIn: 'root' })
export class SessionStore {
  private readonly storage = inject(SESSION_STORAGE);
  private readonly tables = signal<Record<string, StoredTable>>(readTables(this.storage));

  /** Mesas guardadas, da mais recente para a mais antiga. */
  readonly list = computed(() =>
    Object.entries(this.tables())
      .map(([tableId, entry]) => ({ tableId, ...entry }))
      .sort((a, b) => b.savedAt - a.savedAt),
  );

  get(tableId: string): StoredTable | null {
    return this.tables()[tableId] ?? null;
  }

  tokenOf(tableId: string): string | null {
    return this.get(tableId)?.token ?? null;
  }

  save(tableId: string, entry: StoredTable): void {
    if (!TABLE_ID.test(tableId)) {
      return;
    }
    const next = { ...this.tables(), [tableId]: entry };
    const keep = Object.entries(next)
      .sort(([, a], [, b]) => b.savedAt - a.savedAt)
      .slice(0, MAX_TABLES);
    this.commit(Object.fromEntries(keep));
  }

  forget(tableId: string): void {
    this.commit(Object.fromEntries(Object.entries(this.tables()).filter(([id]) => id !== tableId)));
  }

  /** Esquece a mesa se o servidor disse que o token não vale mais (401) ou que a mesa sumiu (404). */
  forgetIfLost(tableId: string, error: unknown): void {
    if (error instanceof ApiFailure && (error.status === 401 || error.status === 404)) {
      this.forget(tableId);
    }
  }

  private commit(tables: Record<string, StoredTable>): void {
    this.tables.set(tables);
    writeTables(this.storage, tables);
  }
}
