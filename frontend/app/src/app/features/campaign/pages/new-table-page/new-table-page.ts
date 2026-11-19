import { ChangeDetectionStrategy, Component, effect, inject, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ENTRY_STEP, HOST_STEPS } from '@shared/game/entry-steps';
import { DvButton } from '@shared/ui/button/button';
import { DvField } from '@shared/ui/field/field';
import { fieldValue } from '@shared/ui/field/field-value';
import { DvInput } from '@shared/ui/field/input';
import { DvIcon } from '@shared/ui/icon/icon';
import { DvNotice } from '@shared/ui/notice/notice';
import { DvOrnament } from '@shared/ui/ornament/ornament';
import { DvSteps } from '@shared/ui/steps/steps';
import { CreateTableStore } from '../../create-table.store';

/**
 * Criar uma mesa: o primeiro passo do caminho do anfitrião (Mesa, Personagem, Sala), no palco das telas de entrada, com
 * os passos à frente do contexto. Fica fora do quadro da campanha, como entrar e personagem. A lista de mesas só aponta para cá; o formulário mora aqui.
 */
@Component({
  selector: 'dv-new-table-page',
  imports: [RouterLink, DvButton, DvField, DvIcon, DvInput, DvNotice, DvOrnament, DvSteps],
  providers: [CreateTableStore],
  templateUrl: './new-table-page.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class NewTablePage {
  /** O id da campanha, da rota `/c/:campaignId`. */
  readonly campaignId = input.required<string>();

  protected readonly fieldValue = fieldValue;
  protected readonly steps = HOST_STEPS;
  protected readonly entryStep = ENTRY_STEP;
  protected readonly store = inject(CreateTableStore);

  constructor() {
    effect(() => this.store.campaignId.set(this.campaignId()));
  }
}
