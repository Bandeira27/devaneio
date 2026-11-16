import { InjectionToken } from '@angular/core';
import { StoredTable, TABLE_ID, isEntry } from './session-entry';

export const STORAGE_KEY = 'devaneio.sessions.v1';

/** O `localStorage` do navegador, ou `null` se ele não existe ou não pode ser lido (janela privada...). */
export const SESSION_STORAGE = new InjectionToken<Storage | null>('SESSION_STORAGE', {
  providedIn: 'root',
  factory: () => {
    try {
      return globalThis.localStorage;
    } catch {
      return null;
    }
  },
});

/** Lê as mesas guardadas. Tudo é validado: armazenamento ausente, JSON quebrado ou entradas fora do formato viram menos mesas, nunca erro. */
export function readTables(storage: Storage | null): Record<string, StoredTable> {
  let parsed: unknown;
  try {
    const raw = storage?.getItem(STORAGE_KEY);
    parsed = raw ? JSON.parse(raw) : null;
  } catch {
    return {};
  }
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    return {};
  }
  const valid: Record<string, StoredTable> = {};
  for (const [tableId, entry] of Object.entries(parsed)) {
    if (TABLE_ID.test(tableId) && isEntry(entry)) {
      valid[tableId] = entry;
    }
  }
  return valid;
}

/** Grava as mesas. Sem espaço ou sem permissão a gravação é ignorada: a sessão segue na memória da aba. */
export function writeTables(storage: Storage | null, tables: Record<string, StoredTable>): void {
  try {
    storage?.setItem(STORAGE_KEY, JSON.stringify(tables));
  } catch {
    // Sem espaço ou sem permissão: some ao fechar a aba.
  }
}
