import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Injector,
  OnInit,
  afterNextRender,
  effect,
  inject,
  input,
} from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { DvButton } from '@shared/ui/button/button';
import { DvIcon } from '@shared/ui/icon/icon';
import { DvNotice } from '@shared/ui/notice/notice';
import { DvState } from '@shared/ui/state/state';
import { focusElement, isFocusFree } from '@shared/ui/focus';
import { BeatsPanel } from '../../host/beats-panel';
import { CopilotPanel } from '../../host/copilot-panel';
import { FactsPanel } from '../../host/facts-panel';
import { TurnTools } from '../../host/turn-tools';
import { WorldPanel } from '../../host/world-panel';
import { TableStore } from '../../table.store';

/**
 * O painel do anfitrião: copiloto e ferramentas do turno de um lado; marcos, fatos, NPCs e locais do outro. Quem não é
 * anfitrião volta para a mesa (o servidor já recusa com 403; isto é conforto). Tem o próprio `TableStore`, que para o
 * fluxo ao vivo ao sair da página.
 */
@Component({
  selector: 'dv-host-page',
  imports: [
    RouterLink,
    DvButton,
    DvIcon,
    DvNotice,
    DvState,
    BeatsPanel,
    CopilotPanel,
    FactsPanel,
    TurnTools,
    WorldPanel,
  ],
  providers: [TableStore],
  templateUrl: './host-page.html',
  styleUrl: './host-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HostPage implements OnInit {
  readonly tableId = input.required<string>();

  protected readonly store = inject(TableStore);
  private readonly router = inject(Router);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly injector = inject(Injector);

  constructor() {
    effect(() => {
      if (this.store.state() === 'ready' && !this.store.isHost()) {
        void this.router.navigate(['/mesa', this.tableId()], { replaceUrl: true });
      }
    });
    effect(() => {
      // Cada estado tem o seu `h1`: o foco passa ao da tela nova quando o da abertura some.
      this.store.state();
      afterNextRender(
        () => {
          const heading = this.host.nativeElement.querySelector('h1');
          if (heading && isFocusFree()) {
            focusElement(heading);
          }
        },
        { injector: this.injector },
      );
    });
  }

  ngOnInit(): void {
    this.store.tableId.set(this.tableId());
    void this.store.load();
  }
}
