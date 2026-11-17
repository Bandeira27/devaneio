import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  inject,
  viewChild,
} from '@angular/core';
import { NavigationEnd, Router, RouterLink, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';
import { DvBrand } from '@shared/ui/brand/brand';
import { DvState } from '@shared/ui/state/state';
import { RoutePending } from './route-pending';

/**
 * O shell do app: link de pular, cabeçalho com a marca e o contêiner por onde as páginas entram. Depois de cada
 * navegação o foco vai para o `h1` da nova tela, para o leitor de tela dizer onde o usuário chegou. Quando a troca de
 * tela demora (`RoutePending`), uma folha de transição cobre a página que está saindo, em vez de deixá-la parada.
 */
@Component({
  selector: 'dv-shell',
  imports: [RouterLink, RouterOutlet, DvBrand, DvState],
  providers: [RoutePending],
  templateUrl: './shell.html',
  styleUrl: './shell.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Shell {
  protected readonly pending = inject(RoutePending);
  private readonly main = viewChild.required<ElementRef<HTMLElement>>('main');
  private waiting: ReturnType<typeof setTimeout> | undefined;

  constructor() {
    const subscription = inject(Router)
      .events.pipe(filter((event) => event instanceof NavigationEnd))
      .subscribe(() => this.focusHeadingWhenReady());
    inject(DestroyRef).onDestroy(() => {
      subscription.unsubscribe();
      clearTimeout(this.waiting);
    });
  }

  /** O link "Pular para o conteúdo": com rota por hash, `href="#..."` navegaria, então o foco é movido à mão. */
  protected skip(event: Event): void {
    event.preventDefault();
    this.main().nativeElement.focus();
  }

  /**
   * Leva o foco ao `h1` da tela nova. Telas que carregam dados só ganham o `h1` depois: espera até 3 s por ele e
   * desiste se o usuário já foi para outro lugar (não rouba o foco de quem está digitando).
   */
  private focusHeadingWhenReady(): void {
    const main = this.main().nativeElement;
    const start = performance.now();
    const attempt = (): void => {
      const heading = main.querySelector('h1');
      const active = document.activeElement;
      // Livre: nada focado, o próprio contêiner ou algo de fora do conteúdo (a marca do cabeçalho). Quem já está num campo do conteúdo não perde o foco.
      const idle =
        active === null || active === document.body || active === main || !main.contains(active);
      if (heading && idle) {
        heading.tabIndex = -1;
        heading.focus({ preventScroll: true });
        return;
      }
      if (!heading && idle && performance.now() - start < 3000) {
        this.waiting = setTimeout(attempt, 100);
      }
    };
    clearTimeout(this.waiting);
    this.waiting = setTimeout(attempt);
  }
}
