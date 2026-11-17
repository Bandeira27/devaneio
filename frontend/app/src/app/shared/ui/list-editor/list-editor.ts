import { NgTemplateOutlet } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Injector,
  TemplateRef,
  afterNextRender,
  contentChild,
  effect,
  inject,
  input,
  output,
  signal,
  viewChild,
} from '@angular/core';
import { DvButton } from '../button/button';
import { DvDisclosure } from '../disclosure/disclosure';
import { DvIcon } from '../icon/icon';
import { focusElement, isFocusFree } from '../focus';

/** O que o template de um item recebe: o item e a posição dele. */
export interface ListItemContext<T> {
  $implicit: T;
  index: number;
}

/** Um pedido de mover o item de uma posição para cima (`-1`) ou para baixo (`1`). */
export interface ListMove {
  index: number;
  delta: -1 | 1;
}

/**
 * Lista editável de itens (locais, NPCs, facções, marcos...): cada item é um bloco recolhido com o nome dele e, aberto,
 * o formulário que o pai projeta em `<ng-template>` (com o item e a posição). Acrescentar, subir, descer e remover são
 * botões com o nome do item no rótulo; o componente só avisa (`add`, `move`, `remove`) e quem tem a lista a muda e
 * decide se confirma. O item acrescentado abre sozinho; depois de uma remoção o foco vai ao botão de acrescentar, para
 * não se perder. Sem itens, mostra `empty`.
 */
@Component({
  selector: 'dv-list-editor',
  imports: [NgTemplateOutlet, DvButton, DvDisclosure, DvIcon],
  templateUrl: './list-editor.html',
  styleUrl: './list-editor.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DvListEditor<T> {
  /** Os itens, na ordem. */
  readonly items = input.required<readonly T[]>();
  /** O nome de um item para o botão e o título (o pai o monta, por exemplo, com o nome do local). */
  readonly nameOf = input.required<(item: T, index: number) => string>();
  /** Como se chama um item novo no botão ("local" dá "Acrescentar local"). */
  readonly noun = input.required<string>();
  /** O que mostrar sem itens. */
  readonly empty = input('Nada por aqui ainda.');
  readonly add = output();
  readonly remove = output<number>();
  readonly move = output<ListMove>();

  protected readonly template = contentChild.required<TemplateRef<ListItemContext<T>>>(TemplateRef);
  private readonly addButton = viewChild<ElementRef<HTMLElement>>('addButton');
  private readonly injector = inject(Injector);
  private readonly opened = signal<ReadonlySet<number>>(new Set());
  private count = -1;

  constructor() {
    effect(() => {
      const length = this.items().length;
      const previous = this.count;
      this.count = length;
      if (previous < 0) {
        return;
      }
      if (length > previous) {
        this.opened.set(new Set([length - 1])); // o item novo abre sozinho, os outros ficam como estavam
      } else if (length < previous) {
        this.opened.set(new Set());
        afterNextRender(
          () => {
            const button = this.addButton()?.nativeElement;
            if (button && isFocusFree()) {
              focusElement(button);
            }
          },
          { injector: this.injector },
        );
      }
    });
  }

  protected isOpen(index: number): boolean {
    return this.opened().has(index);
  }

  protected setOpen(index: number, open: boolean): void {
    const next = new Set(this.opened());
    if (open) {
      next.add(index);
    } else {
      next.delete(index);
    }
    this.opened.set(next);
  }

  protected context(item: T, index: number): ListItemContext<T> {
    return { $implicit: item, index };
  }
}
