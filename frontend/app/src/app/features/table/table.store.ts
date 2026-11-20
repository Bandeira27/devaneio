import { Injectable, OnDestroy, computed, effect, inject, signal, untracked } from '@angular/core';
import type {
  Character,
  EventView,
  RulesView,
  TalkView,
  WeaponInfo,
} from '@contract/api_responses';
import type { LifecycleRequest } from '@contract/api_requests';
import type { TableView } from '@contract/api_responses';
import { firstValueFrom } from 'rxjs';
import { ApiClient } from '@core/api/api-client';
import { isRetryable, messageOf } from '@core/api/api-failure';
import { LiveFeed, LiveStatus } from '@core/live/live-feed';
import { TableLive } from '@core/live/table-live';
import { SessionStore } from '@core/session/session-store';
import { buildFeed } from '@shared/game/feed';
import { revealTextLength } from '@shared/game/reveal';
import { llmNoticeOf } from '@shared/game/llm-notice';
import type { LoadState } from '@shared/game/load-state';
import { hostViewOf } from '@shared/game/host';
import { plainNote, usableWeapons } from '@shared/game/rules';
import { TableActions } from './table.actions';
import { TableChat } from './table.chat';
import {
  blockedReasonOf,
  characterOf,
  connectionBlockOf,
  sceneFor,
  targetsOf,
  turnStatusOf,
} from './table.derived';
import { REVEAL_CLOCK, RevealQueue } from './table.reveal';
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
  /** Todo texto novo espera a sua vez aqui: feed, painel lateral e resposta do dock aparecem juntos e em ordem. */
  private readonly queue = new RevealQueue(inject(REVEAL_CLOCK));
  /** As chaves do feed que já podem aparecer: o histórico da abertura e o que a fila já revelou. */
  private readonly released = signal<ReadonlySet<string>>(new Set());
  /** As chaves que já entraram na fila ou no histórico (cada item novo é enfileirado uma vez só). */
  private readonly known = new Set<string>();
  private seeded = false;

  readonly table = this.snapshot.table;
  readonly campaign = this.snapshot.campaign;
  /** A resposta da última ação sem evento, já na vez dela na fila da história (`RevealQueue`). */
  readonly reply = signal('');
  readonly actionBusy = this.actions.busy;
  readonly saying = this.actions.saying;
  readonly actionError = this.actions.error;
  readonly thinking = this.actions.thinking;

  readonly liveStatus = computed<LiveStatus>(() => this.feed()?.status() ?? 'connecting');
  readonly events = computed<EventView[]>(() => this.feed()?.events() ?? []);
  readonly talk = computed<TalkView[]>(() => this.feed()?.talk() ?? []);
  /** O chat da mesa: mensagens, não lidas e envio. */
  readonly chat = new TableChat(
    this.api,
    () => this.tableId(),
    computed(() => this.feed()?.chat() ?? []),
    computed(() => this.table()?.you ?? ''),
    (message) => this.feed()?.addChat(message),
    computed(() => this.table()?.players ?? []),
  );
  /** Dá para escrever no chat até a partida ser encerrada (a pausa trava só as ações do jogo). */
  readonly canChat = computed(() => this.phase() !== 'ended');

  readonly turn = computed(() => this.table()?.state.turn ?? 0);
  readonly status = computed(() => this.table()?.status ?? 'active');
  /** A fase da mesa; sem a mesa lida ainda, a que não trava nada. */
  readonly phase = computed(() => this.table()?.phase ?? 'running');
  /** O relógio de jogo como o servidor o contou na última leitura, e quando ela chegou. */
  readonly playClock = computed(() => ({
    seconds: this.table()?.elapsed_seconds ?? 0,
    running: this.phase() === 'running',
    receivedAt: this.snapshot.receivedAt(),
  }));
  /** Uma mudança de fase está a caminho. */
  readonly lifecycleBusy = signal(false);
  readonly lifecycleError = signal('');
  readonly isHost = computed(() => this.table()?.role === 'host');
  readonly llmNotice = computed(() => llmNoticeOf(this.table()));
  readonly canSay = computed(() => this.table()?.llm.enabled === true);
  readonly title = computed(() => this.table()?.campaign.title ?? '');
  /** Para onde "voltar" leva: as mesas da campanha desta mesa, ou o início se ainda não se sabe qual é. */
  readonly backLink = computed<string[]>(() => {
    const id = this.table()?.campaign.id;
    return id ? ['/c', id, 'mesas'] : ['/'];
  });
  readonly party = computed<Character[]>(() => Object.values(this.table()?.state.characters ?? {}));
  readonly character = computed(() => characterOf(this.table()));
  readonly scene = computed(() => sceneFor(this.table(), this.campaign()));
  private readonly allItems = computed(() => buildFeed(this.events(), this.talk(), this.turn()));
  /**
   * A foto da mesa que a tela mostra (cena, grupo, ficha): só avança para a mais nova quando todo texto daquela
   * revisão já apareceu. A foto viva (`table`) continua decidindo o que se pode fazer: o botão não libera por espera.
   */
  readonly shownTable = signal<TableView | null>(null);
  readonly shownScene = computed(() => sceneFor(this.shownTable(), this.campaign()));
  readonly shownParty = computed<Character[]>(() =>
    Object.values(this.shownTable()?.state.characters ?? {}),
  );
  readonly shownCharacter = computed(() => characterOf(this.shownTable()));
  /** O feed da mesa; a nota de como foi resolvido sai em palavras de quem joga (`plainNote`), não com os códigos do sistema. */
  readonly feedItems = computed(() => {
    const released = this.released();
    const items = this.allItems().filter((item) => released.has(item.key));
    const attributes = this.rules()?.attributes ?? [];
    return attributes.length === 0
      ? items
      : items.map((item) =>
          item.type === 'event' ? { ...item, note: plainNote(item.note, attributes) } : item,
        );
  });
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
  /** O que só o anfitrião vê (marcos, fatos, NPCs, locais), ou `null` para o jogador e enquanto carrega. */
  readonly host = computed(() =>
    this.isHost() ? hostViewOf(this.campaign(), this.table()?.state ?? null) : null,
  );

  constructor() {
    effect(() => this.syncReveal());
    effect(() => {
      // A primeira carga traz o histórico do chat: o que já existia ao abrir a mesa não é "não lido".
      if (this.liveStatus() === 'live') {
        untracked(() => this.chat.baseline());
      }
    });
    effect(() => {
      const text = this.actions.reply();
      untracked(() => {
        if (text === '') {
          this.reply.set('');
        } else {
          this.queue.enqueue(text.length, () => {
            if (this.actions.reply() === text) {
              this.reply.set(text); // uma resposta dispensada ou trocada no meio da espera não volta
            }
          });
        }
      });
    });
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

  /**
   * Põe na fila o texto novo do feed e decide qual foto da mesa a tela mostra. Os dois passos andam juntos, nesta ordem:
   * se a foto fosse avaliada antes de o evento entrar na fila, a cena nova apareceria antes da narração.
   */
  private syncReveal(): void {
    const items = this.allItems();
    const table = this.table();
    const live = this.feed();
    const status = this.liveStatus();
    const revision = live?.revision() ?? 0;
    const idle = this.queue.idle();
    untracked(() => {
      if (!this.seeded) {
        if (status === 'live') {
          // A primeira leitura de cada abertura é o histórico: entra de uma vez, sem fila.
          this.seeded = true;
          items.forEach((item) => this.known.add(item.key));
          this.released.set(new Set(this.known));
        }
      } else {
        this.enqueueNew(items);
      }
      if (table === null) {
        this.shownTable.set(null);
      } else if (
        this.shownTable() === null ||
        (idle && this.queue.idle() && table.revision <= revision)
      ) {
        this.shownTable.set(table);
      }
    });
  }

  private enqueueNew(items: ReturnType<typeof buildFeed>): void {
    let carry: string[] = []; // marcadores de turno aparecem junto do primeiro texto do turno
    for (const item of items) {
      if (this.known.has(item.key)) {
        continue;
      }
      if (item.type === 'turn') {
        carry.push(item.key);
        continue;
      }
      const keys = [...carry, item.key];
      carry = [];
      keys.forEach((key) => this.known.add(key));
      this.queue.enqueue(revealTextLength(item), () =>
        this.released.update((set) => new Set([...set, ...keys])),
      );
    }
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
      this.session.tag(tableId, table.campaign.id); // mesas guardadas antes de o app saber a campanha ganham o id
      this.table.set(table);
      this.rules.set(rules);
      this.campaign.set(campaign);
      this.state.set('ready');
      this.start(table.revision);
    } catch (error) {
      this.session.forgetIfLost(tableId, error);
      this.loadError.set(messageOf(error));
      this.loadRetryable.set(isRetryable(error));
      this.state.set('failed');
    }
  }

  /** Tira da tela a resposta e o erro da última ação. */
  dismissFeedback(): void {
    this.actions.dismiss();
    this.reply.set('');
  }

  /** Relê a mesa agora (a sala de espera faz isso de tempos em tempos: entrar na mesa não gera evento). */
  refresh(): Promise<void> {
    return this.snapshot.refresh();
  }

  /** Inicia, pausa, retoma ou encerra a partida (anfitrião); devolve se o servidor aceitou. */
  async lifecycle(action: LifecycleRequest['action']): Promise<boolean> {
    if (this.lifecycleBusy()) {
      return false;
    }
    this.lifecycleBusy.set(true);
    this.lifecycleError.set('');
    try {
      const table = await firstValueFrom(
        this.api.lifecycle(this.tableId(), { action, revision: this.snapshot.revision() }),
      );
      this.snapshot.table.set(table);
      this.snapshot.receivedAt.set(Date.now());
      void this.snapshot.refresh();
      return true;
    } catch (error) {
      this.lifecycleError.set(messageOf(error));
      void this.snapshot.refresh(); // a mesa pode ter andado (revisão velha): relê para a próxima tentativa
      return false;
    } finally {
      this.lifecycleBusy.set(false);
    }
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
    this.queue.dispose();
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
