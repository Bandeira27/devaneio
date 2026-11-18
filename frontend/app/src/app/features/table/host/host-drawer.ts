import { ChangeDetectionStrategy, Component, signal } from '@angular/core';
import { DvButton } from '@shared/ui/button/button';
import { BeatsPanel } from './beats-panel';
import { CopilotPanel } from './copilot-panel';
import { FactsPanel } from './facts-panel';
import { LifecycleTools } from './lifecycle-tools';
import { TurnTools } from './turn-tools';
import { WorldPanel } from './world-panel';

/**
 * O conteúdo da barra do anfitrião: a partida no topo, sempre à vista, e abaixo uma parte de cada vez (Agora, Trama,
 * Mundo), porque a barra é estreita. Serve à barra da tela larga e ao bottom sheet do celular, que só mudam o invólucro.
 */
@Component({
  selector: 'dv-host-drawer',
  imports: [DvButton, BeatsPanel, CopilotPanel, FactsPanel, LifecycleTools, TurnTools, WorldPanel],
  templateUrl: './host-drawer.html',
  styleUrl: './host-drawer.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HostDrawer {
  protected readonly sections = [
    { id: 'agora', label: 'Agora' },
    { id: 'trama', label: 'Trama' },
    { id: 'mundo', label: 'Mundo' },
  ] as const;
  protected readonly section = signal<'agora' | 'trama' | 'mundo'>('agora');
}
