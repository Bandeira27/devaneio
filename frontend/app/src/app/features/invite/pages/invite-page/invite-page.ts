import { ChangeDetectionStrategy, Component, OnInit, effect, inject, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { DvButton } from '@shared/ui/button/button';
import { DvCopyField } from '@shared/ui/copy-field/copy-field';
import { DvDisclosure } from '@shared/ui/disclosure/disclosure';
import { DvField } from '@shared/ui/field/field';
import { DvInput } from '@shared/ui/field/input';
import { DvNotice } from '@shared/ui/notice/notice';
import { DvOrnament } from '@shared/ui/ornament/ornament';
import { DvSteps } from '@shared/ui/steps/steps';
import { InviteStore } from '../../invite.store';
import { fieldValue } from '@shared/ui/field/field-value';

/** Tela do convite do anfitrião: o link para mandar aos jogadores. */
@Component({
  selector: 'dv-invite-page',
  imports: [
    RouterLink,
    DvButton,
    DvCopyField,
    DvDisclosure,
    DvField,
    DvInput,
    DvNotice,
    DvOrnament,
    DvSteps,
  ],
  providers: [InviteStore],
  templateUrl: './invite-page.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class InvitePage implements OnInit {
  protected readonly fieldValue = fieldValue;
  /** O id da mesa, vindo da rota. */
  readonly tableId = input.required<string>();

  protected readonly store = inject(InviteStore);

  constructor() {
    effect(() => this.store.tableId.set(this.tableId()));
  }

  ngOnInit(): void {
    this.store.tableId.set(this.tableId()); // os inputs já chegaram; o effect só roda depois
  }
}
