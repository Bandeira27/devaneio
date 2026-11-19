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
  | 'close'
  | 'add'
  | 'book'
  | 'table'
  | 'map'
  | 'person'
  | 'flag'
  | 'scroll'
  | 'eye'
  | 'menu'
  | 'back'
  | 'mail'
  | 'panel'
  | 'save'
  | 'copy'
  | 'retry'
  | 'undo'
  | 'trash'
  | 'up'
  | 'down'
  | 'play';

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
  add: 'M12 5v14M5 12h14',
  book: 'M5 4h11a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3V4zM5 17a3 3 0 0 1 3-3h11',
  table: 'M3 10l2-5h14l2 5M3 10h18M6 10v9M18 10v9M9 14h6',
  map: 'M3 6l6-2 6 2 6-2v14l-6 2-6-2-6 2V6zM9 4v14M15 6v14',
  person: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM5 20a7 7 0 0 1 14 0',
  flag: 'M6 21V4M6 5h11l-2 4 2 4H6',
  scroll:
    'M8 4h10a1 1 0 0 1 1 1v11a3 3 0 0 1-3 3H6a2 2 0 0 0 2-2V4zM6 6a2 2 0 0 1 2-2M11 9h5M11 13h5',
  eye: 'M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z',
  menu: 'M4 7h16M4 12h16M4 17h16',
  back: 'M19 12H5M11 6l-6 6 6 6',
  mail: 'M4 6h16v12H4zM4 7l8 6 8-6',
  panel: 'M4 5h16v4H4zM4 13h7v6H4zM15 13h5v6h-5',
  save: 'M5 4h11l3 3v13H5V4zM8 4v5h7V4M8 20v-6h8v6',
  copy: 'M9 9h10v11H9zM5 15V4h10',
  retry: 'M20 12a8 8 0 1 1-2.5-5.8M20 4v4h-4',
  undo: 'M9 6L4 11l5 5M4 11h9a6 6 0 0 1 0 8h-3',
  trash: 'M4 7h16M10 7V4h4v3M6 7l1 13h10l1-13M10 11v5M14 11v5',
  up: 'M12 19V5M6 11l6-6 6 6',
  down: 'M12 5v14M6 13l6 6 6-6',
  play: 'M7 4l13 8-13 8V4z',
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
