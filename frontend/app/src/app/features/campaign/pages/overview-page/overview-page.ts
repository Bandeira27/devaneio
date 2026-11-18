import { ChangeDetectionStrategy, Component, computed, effect, inject, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { whenOf } from '@shared/game/when';
import { DvButton } from '@shared/ui/button/button';
import { DvOrnament } from '@shared/ui/ornament/ornament';
import { CampaignStore } from '../../campaign.store';

/**
 * A visão geral de uma campanha: a premissa e o caminho mais curto para jogar, que é continuar a mesa mais recente deste
 * aparelho ou abrir uma nova. Criar a mesa, esquecer e as outras mesas moram na página "Mesas".
 */
@Component({
  selector: 'dv-campaign-overview-page',
  imports: [RouterLink, DvButton, DvOrnament],
  providers: [CampaignStore],
  templateUrl: './overview-page.html',
  styleUrl: './overview-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class OverviewPage {
  /** O id da campanha, da rota `/c/:campaignId`. */
  readonly campaignId = input.required<string>();

  protected readonly store = inject(CampaignStore);
  protected readonly latest = computed(() => this.store.tables()[0] ?? null);
  protected readonly when = (time: number): string => whenOf(time, Date.now());

  constructor() {
    effect(() => this.store.campaignId.set(this.campaignId())); // o id vem da rota e pode mudar
  }
}
