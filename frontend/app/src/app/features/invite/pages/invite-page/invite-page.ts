import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  effect,
  inject,
  input,
  signal,
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { DvButton } from '@shared/ui/button/button';
import { DvCopyField } from '@shared/ui/copy-field/copy-field';
import { DvDisclosure } from '@shared/ui/disclosure/disclosure';
import { DvField } from '@shared/ui/field/field';
import { DvInput } from '@shared/ui/field/input';
import { DvNotice } from '@shared/ui/notice/notice';
import { DvOrnament } from '@shared/ui/ornament/ornament';
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
  /** As opções avançadas abrem sozinhas com o aviso de endereço local (ou um erro) e nunca fecham sozinhas: quem digita o IP não perde o campo. */
  protected readonly advancedOpen = signal(false);

  constructor() {
    effect(() => {
      if (this.store.localWarning() || this.store.addressError() !== '') {
        this.advancedOpen.set(true);
      }
    });
  }

  ngOnInit(): void {
    this.store.tableId.set(this.tableId());
  }
}
