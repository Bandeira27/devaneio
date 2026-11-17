import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { DvIcon } from '../icon/icon';

/**
 * Os passos de um caminho curto (Mesa, Personagem, Jogar): mostra onde a pessoa está e quanto falta. Lista ordenada
 * com `aria-label="Passos"`; o passo atual leva `aria-current="step"` e os anteriores aparecem como feitos. Informação
 * nunca só por cor: o atual diz "(agora)" e os anteriores "(feito)" para o leitor de tela; na tela, traço cheio e um "ok" no número.
 *
 * Contrato: entradas `steps` (rótulos, na ordem) e `current` (índice, de 0); sem teclado nem movimento; em tela estreita
 * quebra em linhas, sem rolagem horizontal.
 */
@Component({
  selector: 'dv-steps',
  imports: [DvIcon],
  template: `
    <ol role="list" aria-label="Passos">
      @for (step of steps(); track $index; let i = $index) {
        <li
          [class.done]="i < current()"
          [class.current]="i === current()"
          [attr.aria-current]="i === current() ? 'step' : null"
        >
          <span class="number" aria-hidden="true">
            @if (i < current()) {
              <dv-icon name="ok" size="sm" />
            } @else {
              {{ i + 1 }}
            }
          </span>
          <span class="label"
            >{{ step }}
            @if (i === current()) {
              <span class="dv-visually-hidden"> (agora)</span>
            } @else if (i < current()) {
              <span class="dv-visually-hidden"> (feito)</span>
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
