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

/**
 * Mede a cena e o grupo (`side`) e a barra de ações (`dock`) da lateral da mesa na tela larga e publica as alturas em
 * `--dv-rail-side-height` e `--dv-rail-dock-height`. As duas peças ficam presas juntas: a barra de ações cola logo abaixo
 * da cena (por margem e por `top`), e a cena só rola por dentro se não couber na janela com a barra embaixo dela.
 */
export function publishRailHeights(
  side: Signal<ElementRef<HTMLElement> | undefined>,
  dock: Signal<ElementRef<HTMLElement> | undefined>,
): void {
  effect((onCleanup) => {
    const sideElement = side()?.nativeElement;
    const dockElement = dock()?.nativeElement;
    if (!sideElement || !dockElement || typeof ResizeObserver === 'undefined') {
      return;
    }
    const root = document.documentElement;
    const publish = (): void => {
      root.style.setProperty(
        '--dv-rail-side-height',
        isWide() ? `${sideElement.offsetHeight}px` : '0px',
      );
      root.style.setProperty(
        '--dv-rail-dock-height',
        isWide() ? `${dockElement.offsetHeight}px` : '0px',
      );
    };
    const observer = new ResizeObserver(publish);
    observer.observe(sideElement);
    observer.observe(dockElement);
    publish();
    onCleanup(() => {
      observer.disconnect();
      root.style.removeProperty('--dv-rail-side-height');
      root.style.removeProperty('--dv-rail-dock-height');
    });
  });
}
