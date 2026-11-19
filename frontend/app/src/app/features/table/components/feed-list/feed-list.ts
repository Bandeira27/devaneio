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
import { DvBadge } from '@shared/ui/badge/badge';
import { DvOrnament } from '@shared/ui/ornament/ornament';
import { DvState } from '@shared/ui/state/state';

/**
 * O fluxo da mesa: narração em destaque, a linha mecânica logo abaixo, falas do mestre como citação e, entre os turnos,
 * um cabeçalho de capítulo com ornamento. O que já passou desbota. Quem decide **quando** um texto novo aparece é a
 * fila da mesa (`RevealQueue`): este componente só recebe o que já pode ser visto, faz a tinta nova entrar e leva a
 * tela, com rolagem suave, a cada item que aparece. O leitor de tela só anuncia o que chega depois do carregamento
 * inicial.
 */
@Component({
  selector: 'dv-feed-list',
  imports: [DvBadge, DvState, DvOrnament],
  templateUrl: './feed-list.html',
  styleUrl: './feed-list.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
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
      const grew = items.length > this.count;
      const first = this.count === 0;
      this.count = items.length;
      if (!grew) {
        return;
      }
      if (first || this.initial === null) {
        this.scrollToEnd(false); // a carga inicial abre no fim da história, sem animar
      } else {
        this.follow(items);
      }
    });
  }

  /** Leva a tela, suavemente, ao último item que acabou de aparecer (o texto, não o marcador de turno). */
  private follow(items: readonly FeedItem[]): void {
    const last = [...items].reverse().find((item) => item.type !== 'turn');
    if (last === undefined) {
      return;
    }
    queueMicrotask(() => {
      const element = this.host.nativeElement.querySelector(`[data-key="${CSS.escape(last.key)}"]`);
      element?.scrollIntoView?.({ block: 'nearest', behavior: scrollBehavior() });
    });
  }

  /** Leva a tela ao fim do feed; `smooth` só quando há movimento a mostrar. */
  scrollToEnd(smooth = true): void {
    queueMicrotask(() =>
      this.end().nativeElement.scrollIntoView?.({
        block: 'end',
        behavior: smooth ? scrollBehavior() : 'auto',
      }),
    );
  }
}

/** A rolagem até um texto novo é suave; com movimento reduzido, direta (o que espera é a fila, não o olho). */
function scrollBehavior(): ScrollBehavior {
  return matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth';
}
