import { Injectable, InjectionToken, computed, inject, signal } from '@angular/core';
import { ApiFailure } from '../api/api-failure';

export type StoredRole = 'host' | 'player';

export interface StoredTable {
  token: string;
  playerId: string;
  role: StoredRole;
  /** Título da campanha, para a lista de mesas guardadas. */
  title: string;
  /** Só do anfitrião: o código de convite, para mostrar o link de novo. */
  invite?: string;
  savedAt: number;
}

export const STORAGE_KEY = 'devaneio.sessions.v1';
export const MAX_TABLES = 20;

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

const TABLE_ID = /^[a-f0-9]{16}$/;
const PLAYER_ID = /^p\d{1,3}$/;

function isEntry(value: unknown): value is StoredTable {
  if (typeof value !== 'object' || value === null) {
    return false;
  }
  const v = value as Record<string, unknown>;
  return (
    typeof v['token'] === 'string' &&
    v['token'].length > 0 &&
    v['token'].length <= 200 &&
    typeof v['playerId'] === 'string' &&
    PLAYER_ID.test(v['playerId']) &&
    (v['role'] === 'host' || v['role'] === 'player') &&
    typeof v['title'] === 'string' &&
    v['title'].length <= 200 &&
    (v['invite'] === undefined || (typeof v['invite'] === 'string' && v['invite'].length <= 100)) &&
    typeof v['savedAt'] === 'number' &&
    Number.isFinite(v['savedAt'])
  );
}

/**
 * As mesas em que este navegador entrou (token, `player_id`, papel). O token só viaja no cabeçalho
 * `Authorization`; fica no `localStorage`, que um XSS leria (risco aceito, rule 05 item 24). Tudo que
 * volta do armazenamento é validado, e sem armazenamento a sessão vive só na memória da aba.
 */
@Injectable({ providedIn: 'root' })
export class SessionStore {
  private readonly storage = inject(SESSION_STORAGE);
  private readonly tables = signal<Record<string, StoredTable>>(this.load());

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
    try {
      this.storage?.setItem(STORAGE_KEY, JSON.stringify(tables));
    } catch {
      // Sem espaço ou sem permissão: a sessão segue na memória e some ao fechar a aba.
    }
  }

  private load(): Record<string, StoredTable> {
    let parsed: unknown;
    try {
      const raw = this.storage?.getItem(STORAGE_KEY);
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
}
