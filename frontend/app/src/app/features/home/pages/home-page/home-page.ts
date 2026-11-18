import { ChangeDetectionStrategy, Component, OnInit, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { whenOf } from '@shared/game/when';
import { DvBadge } from '@shared/ui/badge/badge';
import { DvButton } from '@shared/ui/button/button';
import { DvDisclosure } from '@shared/ui/disclosure/disclosure';
import { DvEmblem } from '@shared/ui/emblem/emblem';
import { DvField } from '@shared/ui/field/field';
import { fieldValue } from '@shared/ui/field/field-value';
import { DvInput } from '@shared/ui/field/input';
import { DvIcon } from '@shared/ui/icon/icon';
import { DvOrnament } from '@shared/ui/ornament/ornament';
import { DvState } from '@shared/ui/state/state';
import { HomeStore } from '../../home.store';

/**
 * Tela inicial: as campanhas do servidor em cards (emblema, título, premissa e quantas mesas há neste aparelho). Tocar
 * num card abre a campanha. Quem já tem mesa guardada vê "Continuar de onde parou" no alto; quem recebeu um convite
 * cola o link no fim. Com o editor ligado, o último card é "Nova campanha".
 */
@Component({
  selector: 'dv-home-page',
  imports: [
    RouterLink,
    DvBadge,
    DvButton,
    DvDisclosure,
    DvEmblem,
    DvField,
    DvIcon,
    DvInput,
    DvOrnament,
    DvState,
  ],
  providers: [HomeStore],
  templateUrl: './home-page.html',
  styleUrl: './home-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HomePage implements OnInit {
  protected readonly fieldValue = fieldValue;
  protected readonly store = inject(HomeStore);
  protected readonly when = (time: number): string => whenOf(time, Date.now());

  ngOnInit(): void {
    void this.store.load();
  }
}
