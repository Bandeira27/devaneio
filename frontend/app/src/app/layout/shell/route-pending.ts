import { DestroyRef, Injectable, inject, signal } from '@angular/core';
import {
  NavigationCancel,
  NavigationEnd,
  NavigationError,
  NavigationSkipped,
  NavigationStart,
  Router,
} from '@angular/router';

/** Depois de quanto tempo de espera a folha de transição aparece (antes disso a troca de tela é só a troca). */
export const SHOW_AFTER_MS = 150;
/** Quanto tempo a folha, uma vez aparecida, fica: abre e fecha sem piscar. */
export const MIN_VISIBLE_MS = 300;

/**
 * Diz se há uma navegação demorando o bastante para merecer a folha de transição. Navegação rápida (a maioria, com os
 * módulos pré-carregados) nunca a mostra; uma lenta a mostra depois de `SHOW_AFTER_MS` e a mantém por `MIN_VISIBLE_MS`.
 * Só informa: quem a desenha é o `Shell`.
 */
@Injectable()
export class RoutePending {
  /** Há espera visível agora. */
  readonly visible = signal(false);

  private showTimer: ReturnType<typeof setTimeout> | undefined;
  private hideTimer: ReturnType<typeof setTimeout> | undefined;
  private shownAt = 0;

  constructor() {
    const subscription = inject(Router).events.subscribe((event) => {
      if (event instanceof NavigationStart) {
        this.start();
      } else if (
        event instanceof NavigationEnd ||
        event instanceof NavigationCancel ||
        event instanceof NavigationError ||
        event instanceof NavigationSkipped
      ) {
        this.finish();
      }
    });
    inject(DestroyRef).onDestroy(() => {
      subscription.unsubscribe();
      clearTimeout(this.showTimer);
      clearTimeout(this.hideTimer);
    });
  }

  private start(): void {
    clearTimeout(this.hideTimer);
    if (this.visible()) {
      return; // uma navegação seguida da outra: a folha já está lá e continua
    }
    clearTimeout(this.showTimer);
    this.showTimer = setTimeout(() => {
      this.shownAt = Date.now();
      this.visible.set(true);
    }, SHOW_AFTER_MS);
  }

  private finish(): void {
    clearTimeout(this.showTimer);
    if (!this.visible()) {
      return;
    }
    const left = Math.max(0, MIN_VISIBLE_MS - (Date.now() - this.shownAt));
    clearTimeout(this.hideTimer);
    this.hideTimer = setTimeout(() => this.visible.set(false), left);
  }
}
