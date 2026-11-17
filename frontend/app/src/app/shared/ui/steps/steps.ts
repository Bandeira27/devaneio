import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/**
 * Os passos de um caminho curto (Mesa, Personagem, Jogar): mostra onde a pessoa está e quanto falta. Lista ordenada
 * com `aria-label="Passos"`; o passo atual leva `aria-current="step"` e os anteriores aparecem como feitos. Informação
 * nunca só por cor: o atual tem texto "(agora)" para o leitor de tela e traço cheio; os feitos, um risco.
 *
 * Contrato: entradas `steps` (rótulos, na ordem) e `current` (índice, de 0); sem teclado nem movimento; em tela estreita
 * quebra em linhas, sem rolagem horizontal.
 */
@Component({
  selector: 'dv-steps',
  template: `
    <ol aria-label="Passos">
      @for (step of steps(); track step; let i = $index) {
        <li
          [class.done]="i < current()"
          [class.current]="i === current()"
          [attr.aria-current]="i === current() ? 'step' : null"
        >
          <span class="number" aria-hidden="true">{{ i + 1 }}</span>
          <span class="label"
            >{{ step }}
            @if (i === current()) {
              <span class="dv-visually-hidden"> (agora)</span>
            }
          </span>
        </li>
      }
    </ol>
  `,
  styleUrl: './steps.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DvSteps {
  readonly steps = input.required<readonly string[]>();
  readonly current = input(0);
}
