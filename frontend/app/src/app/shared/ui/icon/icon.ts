import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

/** O conjunto fechado de ícones: as ações do jogo, os tons de status e fechar. */
export type IconName =
  | 'go'
  | 'check'
  | 'attack'
  | 'sheet'
  | 'say'
  | 'command'
  | 'ok'
  | 'warn'
  | 'info'
  | 'danger'
  | 'close';

/** Traços de cada ícone, num quadro de 24 por 24 (só contorno, `currentcolor`). */
const PATHS: Record<IconName, string> = {
  go: 'M5 12h14M13 6l6 6-6 6',
  check:
    'M5 4h14a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1zM9 9h.01M15 9h.01M12 12h.01M9 15h.01M15 15h.01',
  attack: 'M18 3l3 3-9.5 9.5-3-3L18 3zM6.5 13.5l4 4M4 20l3-3',
  sheet: 'M7 3h10a2 2 0 0 1 2 2v15l-3-2-2 2-2-2-2 2-3-2V5a2 2 0 0 1 2-2zM9 8h6M9 12h6',
  say: 'M4 5h16v11H10l-6 4V5z',
  command: 'M4 5h16v14H4zM8 10l3 2-3 2M13 15h4',
  ok: 'M5 12.5l4.5 4.5L19 7',
  warn: 'M12 4l9 16H3L12 4zM12 10v4M12 17h.01',
  info: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 11v5M12 8h.01',
  danger: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM9 9l6 6M15 9l-6 6',
  close: 'M6 6l12 12M18 6L6 18',
};

/**
 * Ícone decorativo: sempre escondido do leitor de tela, então vem junto de um texto (ou o controle que o contém tem
 * nome acessível). Herda a cor do texto.
 */
@Component({
  selector: 'dv-icon',
  template: `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">
    <path [attr.d]="path()" />
  </svg>`,
  styleUrl: './icon.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { 'aria-hidden': 'true', '[class]': "'icon icon--' + size()" },
})
export class DvIcon {
  readonly name = input.required<IconName>();
  readonly size = input<'sm' | 'md'>('md');
  protected readonly path = computed(() => PATHS[this.name()]);
}
