import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  effect,
  input,
  viewChild,
} from '@angular/core';
import type { FeedItem } from '@shared/game/feed';

const NEAR_BOTTOM_PX = 160;

/**
 * O fluxo da mesa: narração em destaque, a linha mecânica como nota de margem, falas do mestre como citação
 * e divisores de turno. O que já passou desbota; texto novo se "revela". Rola para o fim só se quem lê já
 * estava perto dele (não puxa a tela de quem está relendo).
 */
@Component({
  selector: 'dv-feed-list',
  templateUrl: './feed-list.html',
  styleUrl: './feed-list.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FeedList {
  readonly items = input.required<readonly FeedItem[]>();
  private readonly end = viewChild.required<ElementRef<HTMLElement>>('end');
  private count = 0;

  constructor() {
    effect(() => {
      const total = this.items().length;
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
