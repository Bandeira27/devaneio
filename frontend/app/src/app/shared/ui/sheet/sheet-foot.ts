import { ChangeDetectionStrategy, Component } from '@angular/core';

/**
 * Rodapé de uma folha: os botões de ação, com a regra de composição num só lugar (CSS em `styles/sheet.css`).
 * Coloque a ação secundária (voltar, cancelar) antes e a primária por último: ela fica na ponta direita, e um botão
 * sozinho também vai à direita. Um `.dv-note` (como o contador de caracteres) fica à esquerda. Em tela estreita os
 * botões empilham, com a primária embaixo e na largura toda. Rótulos longos quebram em vez de estourar a folha.
 * O host leva a classe `dv-sheet__foot`, que é o que o estilo e os testes enxergam.
 */
@Component({
  selector: 'dv-sheet-foot',
  template: '<ng-content />',
  host: { class: 'dv-sheet__foot' },
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DvSheetFoot {}
