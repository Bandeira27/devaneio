import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  effect,
  input,
  viewChild,
} from '@angular/core';
import type { FeedItem } from '@shared/game/feed';
import { DvDisclosure } from '@shared/ui/disclosure/disclosure';
import { DvState } from '@shared/ui/state/state';

const NEAR_BOTTOM_PX = 160;

/**
 * O fluxo da mesa: narração em destaque, a linha mecânica como nota de margem, falas do mestre como citação
 * e divisores de turno. O que já passou desbota; texto novo se "revela". Rola para o fim só se quem lê já
 * estava perto dele (não puxa a tela de quem está relendo).
 */
@Component({
  selector: 'dv-feed-list',
  imports: [DvDisclosure, DvState],
  templateUrl: './feed-list.html',
  styleUrl: './feed-list.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FeedList {
  readonly items = input.required<readonly FeedItem[]>();
  private readonly end = viewChild.required<ElementRef<HTMLElement>>('end');
  private count = 0;
  private initial: ReadonlySet<string> | null = null;

  /** Só o que chegou depois do carregamento anima a "tinta nova": a carga inicial e a reconexão entram sem animar. */
  protected isNew(key: string): boolean {
    return this.initial !== null && !this.initial.has(key);
  }

  constructor() {
    effect(() => {
      const items = this.items();
      if (this.initial === null && items.length > 0) {
        this.initial = new Set(items.map((item) => item.key));
      }
      const total = items.length;
      const grew = total > this.count;
      const first = this.count === 0;
      this.count = total;
      if (grew && (first || this.nearBottom())) {
        queueMicrotask(() => this.end().nativeElement.scrollIntoView?.({ block: 'end' }));
      }
    });
  }

  private nearBottom(): boolean {
    const el = document.documentElement;
    return el.scrollHeight - (window.scrollY + window.innerHeight) < NEAR_BOTTOM_PX;
  }
}
