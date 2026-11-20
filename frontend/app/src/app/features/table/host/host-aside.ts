import { ChangeDetectionStrategy, Component, output } from '@angular/core';
import { DvButton } from '@shared/ui/button/button';
import { DvIcon } from '@shared/ui/icon/icon';
import { HostDrawer } from './host-drawer';

/** A barra do anfitrião encaixada à direita da mesa (tela larga): o título, o botão de fechar e o conteúdo. */
@Component({
  selector: 'dv-host-aside',
  imports: [DvButton, DvIcon, HostDrawer],
  templateUrl: './host-aside.html',
  styleUrl: './host-aside.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HostAside {
  /** O anfitrião pediu para fechar a barra. */
  readonly closed = output();
}
