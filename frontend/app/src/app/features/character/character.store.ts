import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import type { RulesView, TableView } from '@contract/api_responses';
import { ApiClient } from '@core/api/api-client';
import { messageOf } from '@core/api/api-failure';
import { withStaleRetry } from '@core/api/stale-retry';
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
      if (this.name() === '') {
        this.name.set(me?.name ?? ''); // o personagem nasce com o nome de quem joga; dá para trocar
      }
      this.state.set('ready');
    } catch (error) {
      this.session.forgetIfLost(tableId, error);
      this.loadError.set(messageOf(error));
      this.state.set('failed');
    }
  }

  setName(value: string): void {
    this.name.set(value);
    this.nameError.set('');
    this.error.set('');
  }

  setAttribute(id: string, value: number): void {
    const attribute = this.rules()?.attributes.find((a) => a.id === id);
    if (attribute !== undefined) {
      this.values.update((all) => ({ ...all, [id]: clampAttribute(attribute, value) }));
    }
  }

  /** Os atributos diferem dos valores padrão: só então "Restaurar padrão" faz algo. */
  readonly changed = computed(() => {
    const rules = this.rules();
    if (rules === null) {
      return false;
    }
    const defaults = attributeDefaults(rules);
    return rules.attributes.some(
      (a) => (this.values()[a.id] ?? a.default) !== (defaults[a.id] ?? a.default),
    );
  });

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
      await withStaleRetry(
        (revision) => this.send(name, revision),
        () => this.table()?.revision ?? 0,
        async () => {
          this.table.set(await firstValueFrom(this.api.table(this.tableId())));
        },
      );
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
