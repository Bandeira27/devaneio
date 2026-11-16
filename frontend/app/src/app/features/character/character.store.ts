import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import type { RulesView, TableView } from '@contract/api_responses';
import { ApiClient } from '@core/api/api-client';
import { ApiFailure, messageOf } from '@core/api/api-failure';
import { SessionStore } from '@core/session/session-store';
import { CommandError, join } from '@shared/game/commands';
import { normalizeName, slugify, uniqueId, validateName } from '@shared/game/names';
import { attributeDefaults, clampAttribute } from '@shared/game/rules';
import { llmNoticeOf } from '@shared/game/llm-notice';
import type { LoadState } from '@shared/game/load-state';

/** Criar o personagem: nome e atributos do sistema viram uma linha `entrar` que o motor valida. */
@Injectable()
export class CharacterStore {
  private readonly api = inject(ApiClient);
  private readonly session = inject(SessionStore);
  private readonly router = inject(Router);

  readonly tableId = signal('');
  readonly state = signal<LoadState>('loading');
  readonly loadError = signal('');
  readonly table = signal<TableView | null>(null);
  readonly rules = signal<RulesView | null>(null);
  private readonly taken = signal<string[]>([]);

  readonly name = signal('');
  readonly values = signal<Record<string, number>>({});
  readonly nameError = signal('');
  readonly saving = signal(false);
  readonly error = signal('');

  readonly isHost = computed(() => this.table()?.role === 'host');
  readonly llmNotice = computed(() => llmNoticeOf(this.table()));
  /** O id do personagem: o nome em slug, com sufixo se já houver outro (ou um NPC) com ele. */
  readonly characterId = computed(() =>
    uniqueId(slugify(normalizeName(this.name())), this.taken()),
  );

  async load(): Promise<void> {
    const tableId = this.tableId();
    this.state.set('loading');
    this.loadError.set('');
    try {
      const [table, rules, campaign] = await Promise.all([
        firstValueFrom(this.api.table(tableId)),
        firstValueFrom(this.api.rules(tableId)),
        firstValueFrom(this.api.campaign(tableId)),
      ]);
      const me = table.players.find((player) => player.id === table.you);
      if (me !== undefined && me.character_ids.length > 0) {
        await this.router.navigate(['/mesa', tableId], { replaceUrl: true });
        return;
      }
      this.table.set(table);
      this.rules.set(rules);
      this.taken.set([
        ...Object.keys(table.state.characters),
        ...campaign.npcs.map((npc) => npc.id),
      ]);
      this.values.set(attributeDefaults(rules));
      this.state.set('ready');
    } catch (error) {
      if (error instanceof ApiFailure && (error.status === 401 || error.status === 404)) {
        this.session.forget(tableId); // o token ou a mesa não valem mais neste servidor
      }
      this.loadError.set(messageOf(error));
      this.state.set('failed');
    }
  }

  setAttribute(id: string, value: number): void {
    const attribute = this.rules()?.attributes.find((a) => a.id === id);
    if (attribute !== undefined) {
      this.values.update((all) => ({ ...all, [id]: clampAttribute(attribute, value) }));
    }
  }

  useDefaults(): void {
    const rules = this.rules();
    if (rules !== null) {
      this.values.set(attributeDefaults(rules));
    }
  }

  async submit(): Promise<void> {
    const name = normalizeName(this.name());
    const problem = validateName(name);
    this.nameError.set(problem ?? '');
    this.error.set('');
    const table = this.table();
    if (problem !== null || table === null) {
      return;
    }
    this.saving.set(true);
    try {
      try {
        await this.send(name, table.revision);
      } catch (error) {
        if (!(error instanceof ApiFailure) || error.code !== 'stale_revision') {
          throw error;
        }
        // A mesa andou enquanto o formulário estava aberto: relê a revisão e tenta de novo, uma vez.
        const fresh = await firstValueFrom(this.api.table(this.tableId()));
        this.table.set(fresh);
        await this.send(name, fresh.revision);
      }
    } catch (error) {
      this.error.set(error instanceof CommandError ? error.message : messageOf(error));
    } finally {
      this.saving.set(false);
    }
  }

  private async send(name: string, revision: number): Promise<void> {
    const line = join(this.characterId(), name, this.values());
    await firstValueFrom(this.api.command(this.tableId(), { line, revision }));
    await this.router.navigate(['/mesa', this.tableId()]);
  }
}
