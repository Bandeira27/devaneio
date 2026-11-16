import { DIALOG_DATA, Dialog } from '@angular/cdk/dialog';
import { createGlobalPositionStrategy } from '@angular/cdk/overlay';
import { Injectable, InjectionToken, Injector, Type, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';

/** Dados que quem abre a folha passa ao componente dela. */
export const SHEET_DATA = DIALOG_DATA as InjectionToken<unknown>;

/** A folha vista de dentro: o componente dela fecha a folha, devolvendo um resultado, por aqui. */
export abstract class SheetRef<R = unknown> {
  abstract close(result?: R): void;
}

export interface SheetOptions {
  /** Nome da folha para o leitor de tela. */
  label: string;
  data?: unknown;
}

/**
 * Folha que sobe do pé da tela (diálogo modal do CDK com foco preso, Esc para fechar e foco devolvido a quem
 * abriu). O visual está em `styles/ui.css`. Resolve com o resultado, ou `undefined` se foi fechada sem escolher.
 */
@Injectable({ providedIn: 'root' })
export class Sheet {
  private readonly dialog = inject(Dialog);
  private readonly injector = inject(Injector);

  open<R = void>(component: Type<unknown>, options: SheetOptions): Promise<R | undefined> {
    const ref = this.dialog.open<R>(component, {
      ariaLabel: options.label,
      data: options.data,
      panelClass: 'dv-sheet',
      backdropClass: 'dv-sheet-backdrop',
      autoFocus: 'first-tabbable',
      restoreFocus: true,
      positionStrategy: createGlobalPositionStrategy(this.injector)
        .bottom('0')
        .centerHorizontally(),
      providers: (dialogRef) => [
        { provide: SheetRef, useValue: { close: (result?: R) => dialogRef.close(result) } },
      ],
    });
    return firstValueFrom(ref.closed, { defaultValue: undefined });
  }
}
