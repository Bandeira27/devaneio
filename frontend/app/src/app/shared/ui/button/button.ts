import { Directive, input } from '@angular/core';

export type ButtonVariant = 'primary' | 'ghost';

/**
 * Botão do Devaneio sobre o `<button>` ou `<a>` nativo (a semântica e o teclado ficam do navegador).
 * `<button dvButton="primary">`; sem valor é o botão discreto. O visual está em `styles/ui.css`.
 */
@Directive({
  selector: '[dvButton]',
  host: {
    class: 'dv-button',
    '[class.dv-button--primary]': "variant() === 'primary'",
  },
})
export class DvButton {
  readonly variant = input<ButtonVariant, ButtonVariant | ''>('ghost', {
    alias: 'dvButton',
    transform: (value) => value || 'ghost',
  });
}
