import { DestroyRef, Injectable, inject, signal } from '@angular/core';
import {
  NavigationCancel,
  NavigationEnd,
  NavigationError,
  NavigationSkipped,
  NavigationStart,
  Router,
} from '@angular/router';

/** O que a tela diz (e o leitor de tela ouve) enquanto a troca de tela demora. */
export const OPENING_TEXT = 'Abrindo…';

/** Depois de quanto tempo de espera a folha de transição aparece (antes disso a troca de tela é só a troca). */
export const SHOW_AFTER_MS = 150;

/**
 * Diz o estado da navegação em curso. `busy` vale do começo ao fim de toda navegação (é o `aria-busy` da região
 * principal); `visible` só vale quando a espera passou de `SHOW_AFTER_MS` (é a folha de transição). Os dois caem **no
 * instante em que a navegação acaba**: a tela pronta nunca fica esperando a folha. Só informa: quem desenha é o `Shell`.
 */
@Injectable()
export class RoutePending {
  /** Há uma navegação em curso. */
  readonly busy = signal(false);
  /** A espera já passou do limite: a folha de transição deve aparecer. */
  readonly visible = signal(false);

  private showTimer: ReturnType<typeof setTimeout> | undefined;

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
    });
  }

  private start(): void {
    this.busy.set(true);
    clearTimeout(this.showTimer);
    if (!this.visible()) {
      this.showTimer = setTimeout(() => this.visible.set(true), SHOW_AFTER_MS);
    }
  }

  private finish(): void {
    clearTimeout(this.showTimer);
    this.busy.set(false);
    this.visible.set(false);
  }
}
