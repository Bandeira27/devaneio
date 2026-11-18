import { ElementRef, Signal, effect } from '@angular/core';
import { isWide } from '@shared/ui/wide';

/**
 * Mede a barra de ações e publica a altura em `--dv-dock-height` na raiz do documento, para a rolagem e o foco pararem
 * acima dela (`scroll-padding-bottom` em `styles/base.css`). Só no celular a barra cobre o pé da tela; na tela larga ela
 * fica numa coluna e a altura é zero. Chamar no construtor (precisa de contexto de injeção); limpa ao destruir.
 */
export function publishDockHeight(dock: Signal<ElementRef<HTMLElement> | undefined>): void {
  effect((onCleanup) => {
    const element = dock()?.nativeElement;
    if (!element || typeof ResizeObserver === 'undefined') {
      return;
    }
    const root = document.documentElement;
    const publish = (): void => {
      root.style.setProperty('--dv-dock-height', isWide() ? '0px' : `${element.offsetHeight}px`);
    };
    const observer = new ResizeObserver(publish);
    observer.observe(element);
    publish();
    onCleanup(() => {
      observer.disconnect();
      root.style.removeProperty('--dv-dock-height');
    });
  });
}

/**
 * Mede a linha de situação presa no topo (só no celular) e publica a altura em `--dv-situation-height`, para o que
 * ganha foco ao voltar com Shift+Tab não ficar escondido embaixo dela (`scroll-padding-top` em `styles/base.css`).
 */
export function publishSituationHeight(bar: Signal<ElementRef<HTMLElement> | undefined>): void {
  effect((onCleanup) => {
    const element = bar()?.nativeElement;
    if (!element || typeof ResizeObserver === 'undefined') {
      return;
    }
    const root = document.documentElement;
    const publish = (): void => {
      root.style.setProperty(
        '--dv-situation-height',
        isWide() ? '0px' : `${element.offsetHeight}px`,
      );
    };
    const observer = new ResizeObserver(publish);
    observer.observe(element);
    publish();
    onCleanup(() => {
      observer.disconnect();
      root.style.removeProperty('--dv-situation-height');
    });
  });
}
