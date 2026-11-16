import { Injectable, OnDestroy, computed, effect, inject, signal, untracked } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import type {
  Campaign,
  CampaignView,
  Character,
  EventView,
  GameState,
  NpcView,
  RulesView,
  WeaponInfo,
  TableView,
  TalkView,
} from '@contract/api_responses';
import { ApiClient } from '@core/api/api-client';
import { ApiFailure, messageOf } from '@core/api/api-failure';
import { LiveFeed, LiveStatus } from '@core/live/live-feed';
import { TableLive } from '@core/live/table-live';
import { SessionStore } from '@core/session/session-store';
import { buildFeed } from '@shared/game/feed';
import {
  ACT_BLOCK_TEXT,
  AttackTarget,
  actBlock,
  attackTargets,
  usableWeapons,
} from '@shared/game/rules';
import { sceneOf } from '@shared/game/scene';

export type TableState = 'loading' | 'ready' | 'failed';

/** A mesa em jogo: a foto da mesa (`GET /tables/{id}`), a cena e o fluxo ao vivo, que a mantém atualizada. */
@Injectable()
export class TableStore implements OnDestroy {
  private readonly api = inject(ApiClient);
  private readonly session = inject(SessionStore);
  private readonly liveFactory = inject(TableLive);

  readonly tableId = signal('');
  readonly state = signal<TableState>('loading');
  readonly loadError = signal('');
  readonly table = signal<TableView | null>(null);
  readonly rules = signal<RulesView | null>(null);
  readonly campaign = signal<Campaign | CampaignView | null>(null);
  private readonly feed = signal<LiveFeed | null>(null);
  private refreshing: Promise<void> | null = null;

  readonly liveStatus = computed<LiveStatus>(() => this.feed()?.status() ?? 'connecting');
  readonly events = computed<EventView[]>(() => this.feed()?.events() ?? []);
  readonly talk = computed<TalkView[]>(() => this.feed()?.talk() ?? []);

  readonly turn = computed(() => this.table()?.state.turn ?? 0);
  readonly status = computed(() => this.table()?.status ?? 'active');
  readonly isHost = computed(() => this.table()?.role === 'host');
  readonly llmNotice = computed(() => {
    const llm = this.table()?.llm;
    return llm?.enabled === true && llm.notice ? llm.notice : '';
  });
  readonly title = computed(() => this.table()?.campaign.title ?? '');
  readonly party = computed<Character[]>(() => Object.values(this.table()?.state.characters ?? {}));
  /** O personagem de quem está olhando (o primeiro do jogador), ou `null` se ainda não criou. */
  readonly character = computed<Character | null>(() => {
    const table = this.table();
    const id = table?.players.find((p) => p.id === table.you)?.character_ids[0];
    return (id !== undefined ? table?.state.characters[id] : undefined) ?? null;
  });
  readonly scene = computed(() => {
    const table = this.table();
    const campaign = this.campaign();
    if (table === null || campaign === null) {
      return null;
    }
    const hostNpcs = table.role === 'host' ? (table.state as GameState).npcs : {};
    return sceneOf(campaign, table.state.current_location_id, hostNpcs);
  });
  readonly feedItems = computed(() => buildFeed(this.events(), this.talk(), this.turn()));
  /** Por que o personagem não pode agir agora (texto), ou `''` se pode. */
  readonly blockedReason = computed(() => {
    const table = this.table();
    const rules = this.rules();
    if (table === null || rules === null) {
      return '';
    }
    const block = actBlock({
      character: this.character(),
      turn: this.turn(),
      acted: table.acted,
      status: table.status,
      rules,
    });
    return block === null ? '' : ACT_BLOCK_TEXT[block];
  });

  /** Resposta de comando que não gerou evento (`olhar`, `ficha`...): aparece até a próxima ação. */
  readonly reply = signal('');
  readonly actionBusy = signal(false);
  readonly actionError = signal('');
  readonly canSay = computed(() => this.table()?.llm.enabled === true);
  readonly weapons = computed<WeaponInfo[]>(() => {
    const rules = this.rules();
    return rules === null ? [] : usableWeapons(rules, this.character()?.inventory ?? []);
  });
  readonly targets = computed<AttackTarget[]>(() => {
    const table = this.table();
    const scene = this.scene();
    if (table === null || scene === null) {
      return [];
    }
    const views: Record<string, NpcView> = {};
    for (const [id, npc] of Object.entries(table.state.npcs)) {
      // O anfitrião recebe o estado completo (sem `hostile`): só o jogador comum recebe a visão pronta.
      views[id] = {
        alive: npc.alive,
        hp: npc.hp,
        max_hp: npc.max_hp,
        hostile: 'hostile' in npc && npc.hostile,
      };
    }
    return attackTargets(scene.npcs, views);
  });

  constructor() {
    // A cada revisão nova do fluxo, relê a foto da mesa: hp, turno, quem já agiu, onde o grupo está.
    effect(() => {
      const feed = this.feed();
      const revision = feed?.revision();
      if (feed === null || revision === undefined) {
        return;
      }
      untracked(() => {
        if (revision !== this.table()?.revision) {
          void this.refresh();
        }
      });
    });
  }

  private destroyed = false;
  private again = false;

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
      if (this.destroyed) {
        return; // saiu da página no meio da carga: não abre um laço que ninguém vai parar
      }
      this.table.set(table);
      this.rules.set(rules);
      this.campaign.set(campaign);
      this.state.set('ready');
      this.start(table.revision);
    } catch (error) {
      this.fail(error);
    }
  }

  /**
   * Relê a mesa e a cena. Quem chama durante uma leitura em voo recebe uma leitura começada depois do pedido:
   * o laço repete enquanto chegar pedido novo, então a foto nunca fica atrás da revisão que motivou a chamada.
   */
  refresh(): Promise<void> {
    this.again = true;
    this.refreshing ??= this.drain();
    return this.refreshing;
  }

  private async drain(): Promise<void> {
    try {
      while (this.again && !this.destroyed) {
        this.again = false;
        try {
          const id = this.tableId();
          const [table, campaign] = await Promise.all([
            firstValueFrom(this.api.table(id)),
            firstValueFrom(this.api.campaign(id)),
          ]);
          this.table.set(table);
          this.campaign.set(campaign);
        } catch {
          // O fluxo ao vivo já mostra a conexão; a próxima revisão tenta de novo.
          this.again = false;
        }
      }
    } finally {
      this.refreshing = null;
    }
  }

  /** Manda uma linha de comando. Se a mesa andou (`stale_revision`), relê e tenta de novo, uma vez. */
  async run(line: string): Promise<boolean> {
    return this.act(async () => {
      const send = async (revision: number) =>
        firstValueFrom(this.api.command(this.tableId(), { line, revision }));
      const result = await this.withRetry(send);
      this.reply.set(result.events.length === 0 ? result.text : '');
    });
  }

  /** Texto livre para o mestre de IA (o servidor propõe e aplica as ações, ou só responde). */
  async say(text: string): Promise<boolean> {
    return this.act(async () => {
      const send = async (revision: number) =>
        firstValueFrom(this.api.say(this.tableId(), { text, revision }));
      const result = await this.withRetry(send);
      this.reply.set(result.events.length === 0 ? result.say : '');
    });
  }

  private async act(work: () => Promise<void>): Promise<boolean> {
    if (this.actionBusy()) {
      return false;
    }
    this.actionBusy.set(true);
    this.actionError.set('');
    this.reply.set('');
    try {
      await work();
      void this.refresh();
      return true;
    } catch (error) {
      this.actionError.set(messageOf(error));
      return false;
    } finally {
      this.actionBusy.set(false);
    }
  }

  private async withRetry<T>(send: (revision: number) => Promise<T>): Promise<T> {
    try {
      return await send(this.table()?.revision ?? 0);
    } catch (error) {
      if (!(error instanceof ApiFailure) || error.code !== 'stale_revision') {
        throw error;
      }
      await this.refresh();
      return send(this.table()?.revision ?? 0);
    }
  }

  ngOnDestroy(): void {
    this.destroyed = true;
    this.feed()?.stop();
  }

  private start(revision: number): void {
    this.feed()?.stop();
    const feed = this.liveFactory.open(this.tableId(), revision);
    this.feed.set(feed);
    void feed.run().then(() => {
      if (feed.status() === 'expired') {
        this.session.forget(this.tableId()); // o token não vale mais neste servidor
      }
    });
  }

  private fail(error: unknown): void {
    if (error instanceof ApiFailure && (error.status === 401 || error.status === 404)) {
      this.session.forget(this.tableId());
    }
    this.loadError.set(messageOf(error));
    this.state.set('failed');
  }
}
