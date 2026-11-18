import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  effect,
  inject,
  input,
  output,
  signal,
  viewChild,
} from '@angular/core';
import type { FeedItem } from '@shared/game/feed';
import { revealSteps } from '@shared/game/reveal';
import { DvBadge } from '@shared/ui/badge/badge';
import { DvOrnament } from '@shared/ui/ornament/ornament';
import { DvState } from '@shared/ui/state/state';

const NEAR_BOTTOM_PX = 160;

/**
 * O fluxo da mesa: narração em destaque, a linha mecânica logo abaixo, falas do mestre como citação e, entre os turnos,
 * um cabeçalho de capítulo com ornamento. O que já passou desbota; texto novo se "revela". Rola para o fim só se quem
 * lê já estava perto dele (não puxa a tela de quem está relendo) e, nesse caso, conta o que chegou e não foi visto
 * (`unseen`) para a tela oferecer "novas mensagens". O leitor de tela só anuncia o que chega depois do carregamento
 * inicial.
 */
@Component({
  selector: 'dv-feed-list',
  imports: [DvBadge, DvState, DvOrnament],
  templateUrl: './feed-list.html',
  styleUrl: './feed-list.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '(window:scroll)': 'onScroll()', '(click)': 'skip()' }, // o toque pula a espera da fila
})
export class FeedList {
  readonly items = input.required<readonly FeedItem[]>();
  /** A carga inicial já chegou: o que vem depois é novidade (anima e é anunciado). */
  readonly loaded = input(false);
  /** Quantos itens chegaram enquanto quem lê estava longe do fim. Volta a 0 ao chegar perto do fim. */
  readonly unseen = output<number>();
  private readonly end = viewChild.required<ElementRef<HTMLElement>>('end');
  private count = 0;
  private missed = 0;
  private initial: ReadonlySet<string> | null = null;
  private announceTimer: ReturnType<typeof setTimeout> | undefined;
  /** Só depois da carga inicial a região anuncia: o log não lê 50 itens de uma vez. */
  protected readonly announce = signal(false);
  /** A posição na fila (0, 1, 2...) de cada item que chegou depois da carga: um golpe entra um item de cada vez. */
  protected readonly steps = signal<ReadonlyMap<string, number>>(new Map());
  /** Um toque no feed pulou a espera da fila. */
  protected readonly skipped = signal(false);
  private readonly queued = new Set<string>();

  /** Só o que chegou depois do carregamento anima a "tinta nova": a carga inicial e a reconexão entram sem animar. */
  protected isNew(key: string): boolean {
    return this.initial !== null && !this.initial.has(key);
  }

  constructor() {
    inject(DestroyRef).onDestroy(() => clearTimeout(this.announceTimer));
    effect(() => {
      const items = this.items();
      if (this.initial === null && this.loaded()) {
        this.initial = new Set(items.map((item) => item.key));
        this.announceTimer = setTimeout(() => this.announce.set(true));
      }
      if (this.initial !== null) {
        this.queue(items);
      }
      const total = items.length;
      const grew = total > this.count;
      const first = this.count === 0;
      const added = total - this.count;
      this.count = total;
      if (!grew) {
        return;
      }
      if (first || this.nearBottom()) {
        this.scrollToEnd();
      } else {
        this.missed += added;
        this.unseen.emit(this.missed);
      }
    });
  }

  /** Dá a posição na fila aos itens novos deste lote (os já vistos e os da carga inicial ficam como estão). */
  private queue(items: readonly FeedItem[]): void {
    const fresh = items.filter(
      (item) => !this.initial?.has(item.key) && !this.queued.has(item.key),
    );
    if (fresh.length === 0) {
      return;
    }
    const positions = revealSteps(fresh.map((item) => item.type));
    const next = new Map(this.steps());
    fresh.forEach((item, index) => {
      this.queued.add(item.key);
      next.set(item.key, positions[index] ?? 0);
    });
    this.steps.set(next);
    this.skipped.set(false);
  }

  /** Leva a tela ao fim do feed (o que ainda não foi visto passa a ser visto). */
  scrollToEnd(): void {
    queueMicrotask(() => this.end().nativeElement.scrollIntoView?.({ block: 'end' }));
    this.clearMissed();
  }

  protected skip(): void {
    this.skipped.set(true);
  }

  protected onScroll(): void {
    if (this.missed > 0 && this.nearBottom()) {
      this.clearMissed();
    }
  }

  private clearMissed(): void {
    if (this.missed > 0) {
      this.missed = 0;
      this.unseen.emit(0);
    }
  }

  private nearBottom(): boolean {
    const el = document.documentElement;
    return el.scrollHeight - (window.scrollY + window.innerHeight) < NEAR_BOTTOM_PX;
  }
}
