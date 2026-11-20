import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/** O tamanho da marca: no cabeçalho (`md`) ou na abertura de uma tela (`lg`). */
export type BrandSize = 'md' | 'lg';

/**
 * A marca do Devaneio: um selo com a inicial e o nome. É só texto e CSS (sem imagem); o selo é decoração
 * (`aria-hidden`) e o nome é o que o leitor de tela lê. Usada no cabeçalho e na abertura de tela.
 *
 * Contrato: entrada `size` (`md` padrão, `lg`); sem estados nem teclado (quem a envolve num link a torna clicável);
 * sem movimento; em tela estreita não quebra (uma linha).
 */
@Component({
  selector: 'dv-brand',
  templateUrl: './brand.html',
  styleUrl: './brand.css',
  host: { '[class]': "'brand--' + size()" },
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DvBrand {
  readonly size = input<BrandSize>('md');
}
