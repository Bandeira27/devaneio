import { booleanAttribute, DestroyRef, Directive, ElementRef, inject, input } from '@angular/core';

/** O visual de um botão: destaque, discreto ou de perigo (o que remove ou descarta). */
export type ButtonVariant = 'primary' | 'ghost' | 'danger';

/**
 * Botão do Devaneio sobre o `<button>` ou `<a>` nativo (a semântica e o teclado ficam do navegador).
 * `<button dvButton="primary">`; sem valor é o botão discreto; `dvButton="danger"` é para o que remove ou descarta (contorno e texto na cor de erro, sem preenchimento: o perigo chama a atenção sem competir com a ação principal). O visual está em `styles/primitives.css`.
 *
 * Estados: `disabled` nativo para o que não existe agora; **`dvBlocked`** para o que está bloqueado por um motivo
 * (`aria-disabled`, o foco não se perde: ligue o motivo com `aria-describedby`); **`dvLoading`** durante um envio
 * (`aria-busy`, o botão fica bloqueado e um ponto pulsa). Bloqueado e em envio não deixam o clique passar.
 */
@Directive({
  selector: '[dvButton]',
  host: {
    class: 'dv-button',
    '[class.dv-button--primary]': "variant() === 'primary'",
    '[class.dv-button--danger]': "variant() === 'danger'",
    '[class.dv-button--loading]': 'dvLoading()',
    '[attr.aria-busy]': "dvLoading() ? 'true' : null",
    '[attr.aria-disabled]': "dvBlocked() || dvLoading() ? 'true' : null",
  },
})
export class DvButton {
  readonly variant = input<ButtonVariant, ButtonVariant | ''>('ghost', {
    alias: 'dvButton',
    transform: (value) => value || 'ghost',
  });
  /** Bloqueado por um motivo que o usuário pode ler; o botão continua focável. */
  readonly dvBlocked = input(false, { transform: booleanAttribute });
  /** Enviando: bloqueia e mostra o ponto de pendência. */
  readonly dvLoading = input(false, { transform: booleanAttribute });

  constructor() {
    // Na fase de captura, para valer antes dos `(click)` do próprio elemento (o do template roda antes do da diretiva).
    const element = inject<ElementRef<HTMLElement>>(ElementRef).nativeElement;
    const guard = (event: Event): void => {
      if (this.dvBlocked() || this.dvLoading()) {
        event.preventDefault();
        event.stopImmediatePropagation();
      }
    };
    element.addEventListener('click', guard, true);
    inject(DestroyRef).onDestroy(() => element.removeEventListener('click', guard, true));
  }
}
