import { ChangeDetectionStrategy, Component, input, model } from '@angular/core';

/**
 * Detalhe que abre e fecha, sobre o `<details>` nativo (teclado e leitor de tela vêm do navegador). O resumo tem
 * alvo de toque de 44 px; ao abrir, o conteúdo aparece com um fade (onde o navegador suporta `::details-content`).
 * `open` é de duas vias.
 */
@Component({
  selector: 'dv-disclosure',
  templateUrl: './disclosure.html',
  styleUrl: './disclosure.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DvDisclosure {
  readonly label = input.required<string>();
  readonly open = model(false);

  protected toggled(event: Event): void {
    this.open.set((event.target as HTMLDetailsElement).open);
  }
}
