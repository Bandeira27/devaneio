import { ChangeDetectionStrategy, Component } from '@angular/core';

/**
 * Um filete com um losango no meio, que abre a tela de abertura (`dv-state cover`) e separa os turnos do feed. É decoração: SVG
 * inline em `currentColor` (a cor vem de quem o usa), `aria-hidden`, sem foco nem movimento. Ocupa a largura que o
 * contêiner der, até `--dv-measure-ornament`.
 */
@Component({
  selector: 'dv-ornament',
  templateUrl: './ornament.html',
  styleUrl: './ornament.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DvOrnament {}
