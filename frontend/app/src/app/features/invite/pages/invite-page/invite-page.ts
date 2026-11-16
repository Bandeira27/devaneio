import { ChangeDetectionStrategy, Component, OnInit, effect, inject, input } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { DvButton } from '@shared/ui/button/button';
import { DvCopyField } from '@shared/ui/copy-field/copy-field';
import { DvField } from '@shared/ui/field/field';
import { DvInput } from '@shared/ui/field/input';
import { DvNotice } from '@shared/ui/notice/notice';
import { InviteStore } from '../../invite.store';
import { fieldValue } from '@shared/ui/field/field-value';

/** Tela do convite do anfitrião: o link para mandar aos jogadores. */
@Component({
  selector: 'dv-invite-page',
  imports: [RouterLink, DvButton, DvCopyField, DvField, DvInput, DvNotice],
  providers: [InviteStore],
  templateUrl: './invite-page.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class InvitePage implements OnInit {
  protected readonly fieldValue = fieldValue;
  /** O id da mesa, vindo da rota. */
  readonly tableId = input.required<string>();

  protected readonly store = inject(InviteStore);
  private readonly router = inject(Router);

  constructor() {
    effect(() => this.store.tableId.set(this.tableId()));
  }

  ngOnInit(): void {
    this.store.tableId.set(this.tableId()); // os inputs já chegaram; o effect só roda depois
    // Só o anfitrião tem o código; quem chegou aqui sem ele vai direto para a mesa.
    if (!this.store.isHost()) {
      void this.router.navigate(['/mesa', this.tableId(), 'personagem']);
    }
  }
}
