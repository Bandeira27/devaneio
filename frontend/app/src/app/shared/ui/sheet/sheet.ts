import { DIALOG_DATA, Dialog, DialogRef } from '@angular/cdk/dialog';
import { createGlobalPositionStrategy } from '@angular/cdk/overlay';
import { Injectable, InjectionToken, Injector, Type, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { isWide } from '../wide';

/** Dados que quem abre a folha passa ao componente dela. */
export const SHEET_DATA = DIALOG_DATA as InjectionToken<unknown>;

/** A folha vista de dentro: o componente dela fecha a folha, devolvendo um resultado, por aqui. */
export abstract class SheetRef<R = unknown> {
  abstract close(result?: R): void;
}

/** Como abrir uma folha: o nome para o leitor de tela e os dados para o componente. */
export interface SheetOptions {
  /** Nome da folha para o leitor de tela. */
  label: string;
  data?: unknown;
  /** De onde o componente da folha herda seus provedores (por exemplo, o store da página que a abriu). */
  injector?: Injector;
}

/**
 * Folha que sobe do pé da tela no celular e vira diálogo centralizado na tela larga. É um diálogo modal do CDK, com
 * foco preso e devolvido a quem abriu. O visual e o
 * movimento estão em `styles/sheet.css`. Resolve com o resultado, ou `undefined` se foi fechada sem escolher.
 *
 * O CDK remove o painel assim que fecha, então o fechamento é feito aqui: `Esc`, clique no fundo e `SheetRef.close`
 * marcam a folha como saindo, esperam a animação de saída (sem esperar nada se o movimento está reduzido ou não há
 * animação) e só então fecham o diálogo. O estado final nunca espera: nada na tela depende do fim da animação.
 */
@Injectable({ providedIn: 'root' })
export class Sheet {
  private readonly dialog = inject(Dialog);
  private readonly injector = inject(Injector);

  open<R = void>(component: Type<unknown>, options: SheetOptions): Promise<R | undefined> {
    const dialog = isWide(); // tela larga: diálogo no meio
    const ref = this.dialog.open<R>(component, {
      ariaLabel: options.label,
      data: options.data,
      injector: options.injector,
      panelClass: dialog ? ['dv-sheet', 'dv-sheet--dialog'] : 'dv-sheet',
      backdropClass: 'dv-sheet-backdrop',
      disableClose: true, // Esc e fundo passam por `leave`, abaixo, para animar a saída
      autoFocus: 'first-tabbable', // o primeiro campo da folha leva `cdkFocusInitial`
      restoreFocus: true,
      positionStrategy: dialog
        ? createGlobalPositionStrategy(this.injector).centerHorizontally().centerVertically()
        : createGlobalPositionStrategy(this.injector).bottom('0').centerHorizontally(),
      providers: (dialogRef) => [
        { provide: SheetRef, useValue: { close: (result?: R) => this.leave(dialogRef, result) } },
      ],
    });
    ref.keydownEvents.subscribe((event) => {
      if (event.key === 'Escape') {
        this.leave(ref, undefined);
      }
    });
    ref.backdropClick.subscribe(() => this.leave(ref, undefined));
    return firstValueFrom(ref.closed, { defaultValue: undefined });
  }

  /** Anima a saída e fecha o diálogo com o resultado. Chamado várias vezes, só a primeira vale. */
  private leave<R>(ref: DialogRef<R>, result: R | undefined): void {
    const pane = ref.overlayRef.overlayElement;
    if (pane.classList.contains('dv-sheet--leaving')) {
      return;
    }
    pane.classList.add('dv-sheet--leaving');
    ref.overlayRef.backdropElement?.classList.add('dv-sheet-backdrop--leaving');
    const seconds = parseFloat(getComputedStyle(pane).animationDuration);
    let done = false;
    const finish = (): void => {
      if (!done) {
        done = true;
        ref.close(result);
      }
    };
    if (!(seconds > 0)) {
      finish(); // sem animação (jsdom, movimento ausente): fecha já
      return;
    }
    // `animationend` borbulha: só o da própria folha conta (o de um filho não pode cortar a saída).
    pane.addEventListener('animationend', (event) => {
      if (event.target === pane) {
        finish();
      }
    });
    setTimeout(finish, seconds * 1000 * 1.5); // se o fim da animação não vier, não prende a folha
  }
}
