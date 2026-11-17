import { ChangeDetectionStrategy, Component } from '@angular/core';

/**
 * Um filete com um losango no meio, que abre a tela de abertura (`dv-state cover`) e separa os turnos do feed. É decoração: SVG
 * inline em `currentColor` (a cor vem de quem o usa), `aria-hidden`, sem foco nem movimento. Ocupa a largura que o
 * contêiner der, até `--dv-measure-ornament`.
 */
@Component({
  selector: 'dv-ornament',
  template: `
    <svg
      viewBox="0 0 120 8"
      preserveAspectRatio="xMidYMid meet"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M0 4H50M70 4H120" fill="none" stroke="currentColor" stroke-width="1" />
      <path d="M60 0.5L63.5 4L60 7.5L56.5 4Z" fill="currentColor" />
    </svg>
  `,
  styleUrl: './ornament.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DvOrnament {}
