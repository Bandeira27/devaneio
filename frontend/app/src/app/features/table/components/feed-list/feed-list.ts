import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  effect,
  inject,
  input,
  signal,
  viewChild,
} from '@angular/core';
import type { FeedItem } from '@shared/game/feed';
import { REVEAL_MAX_QUEUE, revealSteps, revealWeight } from '@shared/game/reveal';
import { DvBadge } from '@shared/ui/badge/badge';
import { DvOrnament } from '@shared/ui/ornament/ornament';
import { DvState } from '@shared/ui/state/state';

/** Quantos passos a primeira resposta de uma ação espera antes de aparecer: o mestre "pensando" antes de falar. */
const LEAD_STEPS = 1;

/**
 * O fluxo da mesa: narração em destaque, a linha mecânica logo abaixo, falas do mestre como citação e, entre os turnos,
 * um cabeçalho de capítulo com ornamento. O que já passou desbota; texto novo se "revela" em fila, um item de cada vez
 * (cada um espera os anteriores serem lidos, e o primeiro espera um passo, como o mestre pensando). A tela **acompanha**
 * a fila: leva o usuário a cada item no momento em que ele aparece, mesmo de quem está no topo. O leitor de tela só
 * anuncia o que chega depois do carregamento inicial.
 */
@Component({
  selector: 'dv-feed-list',
  imports: [DvBadge, DvState, DvOrnament],
  templateUrl: './feed-list.html',
  styleUrl: './feed-list.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '(click)': 'skip()' }, // o toque pula a espera da fila
})
export class FeedList {
  readonly items = input.required<readonly FeedItem[]>();
  /** A carga inicial já chegou: o que vem depois é novidade (anima e é anunciado). */
  readonly loaded = input(false);
  private readonly end = viewChild.required<ElementRef<HTMLElement>>('end');
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private count = 0;
  private initial: ReadonlySet<string> | null = null;
  private announceTimer: ReturnType<typeof setTimeout> | undefined;
  /** Só depois da carga inicial a região anuncia: o log não lê 50 itens de uma vez. */
  protected readonly announce = signal(false);
  /** A posição na fila (em passos, com a espera inicial) de cada item que chegou depois da carga. */
  protected readonly steps = signal<ReadonlyMap<string, number>>(new Map());
  /** Um toque no feed pulou a espera da fila. */
  protected readonly skipped = signal(false);
  private readonly queued = new Set<string>();
  /** Quando a fila atual termina (relógio da página, em ms): um lote que chega no meio espera o anterior acabar. */
  private queueEndsAt = 0;
  private readonly followTimers = new Set<ReturnType<typeof setTimeout>>();

  /** Só o que chegou depois do carregamento anima a "tinta nova": a carga inicial e a reconexão entram sem animar. */
  protected isNew(key: string): boolean {
    return this.initial !== null && !this.initial.has(key);
  }

  constructor() {
    inject(DestroyRef).onDestroy(() => {
      clearTimeout(this.announceTimer);
      this.clearFollow();
    });
    effect(() => {
      const items = this.items();
      if (this.initial === null && this.loaded()) {
        this.initial = new Set(items.map((item) => item.key));
        this.announceTimer = setTimeout(() => this.announce.set(true));
      }
      if (this.initial !== null) {
        this.queue(items);
      }
      const grew = items.length > this.count;
      const first = this.count === 0;
      this.count = items.length;
      if (grew && (first || this.initial === null)) {
        this.scrollToEnd(); // a carga inicial abre no fim da história
      }
    });
  }

  /** O tempo, em ms, de um passo da fila (`--dv-reveal-step`); zero com movimento reduzido (tudo entra de uma vez). */
  private stepMs(): number {
    const value = parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue('--dv-reveal-step'),
    );
    return Number.isFinite(value) ? value : 0;
  }

  /**
   * Dá a posição na fila aos itens novos deste lote e leva a tela a cada um quando ele aparece. O primeiro espera
   * `LEAD_STEPS` (a resposta não surge junto do toque); um lote que chega com a fila ainda andando espera ela acabar.
   */
  private queue(items: readonly FeedItem[]): void {
    const fresh = items.filter(
      (item) => !this.initial?.has(item.key) && !this.queued.has(item.key),
    );
    if (fresh.length === 0) {
      return;
    }
    if (fresh.filter((item) => item.type !== 'turn').length > REVEAL_MAX_QUEUE) {
      // Uma carga grande (recarga, reconexão): entra tudo de uma vez, sem espera, e a tela vai ao fim.
      const next = new Map(this.steps());
      fresh.forEach((item) => {
        this.queued.add(item.key);
        next.set(item.key, 0);
      });
      this.steps.set(next);
      this.scrollToEnd();
      return;
    }
    const stepMs = this.stepMs();
    const now = performance.now();
    const busy = stepMs > 0 ? Math.max(0, this.queueEndsAt - now) / stepMs : 0;
    const offset = busy > 0 ? busy : LEAD_STEPS;
    const positions = revealSteps(fresh);
    const next = new Map(this.steps());
    let endSteps = offset;
    fresh.forEach((item, index) => {
      const step = offset + (positions[index] ?? 0);
      this.queued.add(item.key);
      next.set(item.key, step);
      if (item.type !== 'turn') {
        endSteps = Math.max(endSteps, step + revealWeight(item));
        this.followTo(item.key, step * stepMs);
      }
    });
    this.queueEndsAt = now + endSteps * stepMs;
    this.steps.set(next);
    this.skipped.set(false);
  }

  /** Leva a tela ao item daqui a `delay` ms (quando ele começa a aparecer): acompanha a fila, sem esperar o fim. */
  private followTo(key: string, delay: number): void {
    const timer = setTimeout(() => {
      this.followTimers.delete(timer);
      const element = this.host.nativeElement.querySelector(`[data-key="${CSS.escape(key)}"]`);
      element?.scrollIntoView?.({ block: 'nearest' });
    }, delay);
    this.followTimers.add(timer);
  }

  private clearFollow(): void {
    this.followTimers.forEach((timer) => clearTimeout(timer));
    this.followTimers.clear();
  }

  /** Leva a tela ao fim do feed. */
  scrollToEnd(): void {
    queueMicrotask(() => this.end().nativeElement.scrollIntoView?.({ block: 'end' }));
  }

  /** O toque pula a espera: tudo aparece e a tela vai ao último item. */
  protected skip(): void {
    this.skipped.set(true);
    this.clearFollow();
    this.queueEndsAt = 0;
    this.scrollToEnd();
  }
}
