import { ChangeDetectionStrategy, Component, OnInit, effect, inject, input } from '@angular/core';
import { Router } from '@angular/router';
import { DvButton } from '@shared/ui/button/button';
import { DvField } from '@shared/ui/field/field';
import { DvInput } from '@shared/ui/field/input';
import { DvNotice } from '@shared/ui/notice/notice';
import { JoinStore } from '../../join.store';
import { fieldValue } from '@shared/ui/field/field-value';

@Component({
  selector: 'dv-join-page',
  imports: [DvButton, DvField, DvInput, DvNotice],
  providers: [JoinStore],
  templateUrl: './join-page.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class JoinPage implements OnInit {
  protected readonly fieldValue = fieldValue;
  /** Da rota: o id da mesa e o código do convite (o código é opcional: quem entra sem o link o cola). */
  readonly tableId = input.required<string>();
  readonly invite = input<string>();

  protected readonly store = inject(JoinStore);
  private readonly router = inject(Router);

  constructor() {
    effect(() => {
      this.store.tableId.set(this.tableId());
      this.store.code.set(this.invite() ?? '');
    });
  }

  ngOnInit(): void {
    this.store.tableId.set(this.tableId()); // os inputs já chegaram; o effect só roda depois
    this.store.code.set(this.invite() ?? '');
    if (this.store.alreadyIn()) {
      void this.router.navigate(['/mesa', this.tableId()]);
    }
  }
}
