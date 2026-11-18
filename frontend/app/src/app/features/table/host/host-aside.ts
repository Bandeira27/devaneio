import { ChangeDetectionStrategy, Component, output } from '@angular/core';
import { DvButton } from '@shared/ui/button/button';
import { DvIcon } from '@shared/ui/icon/icon';
import { HostDrawer } from './host-drawer';

/** A barra do anfitrião encaixada à direita da mesa (tela larga): o título, o botão de fechar e o conteúdo. */
@Component({
  selector: 'dv-host-aside',
  imports: [DvButton, DvIcon, HostDrawer],
  template: `
    <aside id="painel-anfitriao" aria-labelledby="painel-anfitriao-titulo">
      <header class="host-aside__head">
        <h2 id="painel-anfitriao-titulo" class="dv-section host-aside__title" tabindex="-1">
          Painel do anfitrião
        </h2>
        <button
          dvButton
          class="dv-sheet__close"
          type="button"
          aria-label="Fechar o painel"
          (click)="closed.emit()"
        >
          <dv-icon name="close" />
        </button>
      </header>
      <dv-host-drawer />
    </aside>
  `,
  styleUrl: './host-aside.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HostAside {
  /** O anfitrião pediu para fechar a barra. */
  readonly closed = output();
}
