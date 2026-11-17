import { Injectable, OnDestroy, computed, effect, inject, signal, untracked } from '@angular/core';
import type {
  Character,
  EventView,
  RulesView,
  TalkView,
  WeaponInfo,
} from '@contract/api_responses';
import { firstValueFrom } from 'rxjs';
import { ApiClient } from '@core/api/api-client';
import { ApiFailure, messageOf } from '@core/api/api-failure';
import { LiveFeed, LiveStatus } from '@core/live/live-feed';
import { TableLive } from '@core/live/table-live';
import { SessionStore } from '@core/session/session-store';
import { buildFeed } from '@shared/game/feed';
import { llmNoticeOf } from '@shared/game/llm-notice';
import type { LoadState } from '@shared/game/load-state';
import { usableWeapons } from '@shared/game/rules';
import { TableActions } from './table.actions';
import {
  blockedReasonOf,
  characterOf,
  connectionBlockOf,
  sceneFor,
  targetsOf,
  turnStatusOf,
} from './table.derived';
import { TableSnapshot } from './table.snapshot';

/**
 * A mesa em jogo, para as telas: junta a foto da mesa (`TableSnapshot`), o fluxo ao vivo que a mantém atualizada
 * (`LiveFeed`) e as ações do jogador (`TableActions`), e expõe o que a tela mostra como sinais.
 */
@Injectable()
export class TableStore implements OnDestroy {
  private readonly api = inject(ApiClient);
  private readonly session = inject(SessionStore);
  private readonly liveFactory = inject(TableLive);

  readonly tableId = signal('');
  readonly state = signal<LoadState>('loading');
  readonly loadError = signal('');
  /** Vale tentar de novo (rede, tempo, servidor)? Mesa que sumiu ou sessão vencida não melhoram tentando. */
  readonly loadRetryable = signal(true);
  readonly rules = signal<RulesView | null>(null);
  private readonly snapshot = new TableSnapshot(this.api, () => this.tableId());
  private readonly actions = new TableActions(this.api, () => this.tableId(), this.snapshot);
  private readonly feed = signal<LiveFeed | null>(null);
  private destroyed = false;

  readonly table = this.snapshot.table;
  readonly campaign = this.snapshot.campaign;
  readonly reply = this.actions.reply;
  readonly actionBusy = this.actions.busy;
  readonly actionError = this.actions.error;
  readonly thinking = this.actions.thinking;

  readonly liveStatus = computed<LiveStatus>(() => this.feed()?.status() ?? 'connecting');
  readonly events = computed<EventView[]>(() => this.feed()?.events() ?? []);
  readonly talk = computed<TalkView[]>(() => this.feed()?.talk() ?? []);

  readonly turn = computed(() => this.table()?.state.turn ?? 0);
  readonly status = computed(() => this.table()?.status ?? 'active');
  readonly isHost = computed(() => this.table()?.role === 'host');
  readonly llmNotice = computed(() => llmNoticeOf(this.table()));
  readonly canSay = computed(() => this.table()?.llm.enabled === true);
  readonly title = computed(() => this.table()?.campaign.title ?? '');
  readonly party = computed<Character[]>(() => Object.values(this.table()?.state.characters ?? {}));
  readonly character = computed(() => characterOf(this.table()));
  readonly scene = computed(() => sceneFor(this.table(), this.campaign()));
  readonly feedItems = computed(() => buildFeed(this.events(), this.talk(), this.turn()));
  readonly blockedReason = computed(
    () =>
      connectionBlockOf(this.liveStatus()) ||
      blockedReasonOf(this.table(), this.rules(), this.character()),
  );
  readonly turnStatus = computed(() => turnStatusOf(this.table(), this.rules(), this.character()));
  readonly weapons = computed<WeaponInfo[]>(() => {
    const rules = this.rules();
    return rules === null ? [] : usableWeapons(rules, this.character()?.inventory ?? []);
  });
  readonly targets = computed(() => targetsOf(this.table(), this.scene()));

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
          void this.snapshot.refresh();
        }
      });
    });
  }

  /** Lê a mesa, as regras e a cena e abre o fluxo ao vivo. */
  async load(): Promise<void> {
    const tableId = this.tableId();
    this.state.set('loading');
    this.loadError.set('');
    this.loadRetryable.set(true);
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
      this.session.forgetIfLost(tableId, error);
      this.loadError.set(messageOf(error));
      this.loadRetryable.set(!(error instanceof ApiFailure) || error.retryable);
      this.state.set('failed');
    }
  }

  /** Tira da tela a resposta e o erro da última ação. */
  dismissFeedback(): void {
    this.actions.dismiss();
  }

  /** Manda uma linha de comando; devolve se o servidor a aceitou. */
  run(line: string): Promise<boolean> {
    return this.actions.run(line);
  }

  /** Manda um texto livre ao mestre de IA; devolve se o servidor o aceitou. */
  say(text: string): Promise<boolean> {
    return this.actions.say(text);
  }

  ngOnDestroy(): void {
    this.destroyed = true;
    this.snapshot.stop();
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
}
