import { ChangeDetectionStrategy, Component, OnInit, computed, inject, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ENTRY_STEP, GUEST_STEPS } from '@shared/game/entry-steps';
import { DvButton } from '@shared/ui/button/button';
import { DvField } from '@shared/ui/field/field';
import { DvInput } from '@shared/ui/field/input';
import { DvNotice } from '@shared/ui/notice/notice';
import { DvOrnament } from '@shared/ui/ornament/ornament';
import { DvSteps } from '@shared/ui/steps/steps';
import { JoinStore } from '../../join.store';
import { fieldValue } from '@shared/ui/field/field-value';
import { DvIcon } from '../../../../shared/ui/icon/icon';

/** Tela de entrar numa mesa: o nome do jogador e o convite que veio no link. */
@Component({
  selector: 'dv-join-page',
  imports: [RouterLink, DvIcon, DvButton, DvField, DvInput, DvNotice, DvOrnament, DvSteps],
  providers: [JoinStore],
  templateUrl: './join-page.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class JoinPage implements OnInit {
  protected readonly fieldValue = fieldValue;
  protected readonly steps = GUEST_STEPS;
  protected readonly entryStep = ENTRY_STEP;
  /** Da rota: o id da mesa e o código do convite (o código é opcional: quem entra sem o link o cola). */
  readonly tableId = input.required<string>();
  readonly invite = input<string>();

  protected readonly store = inject(JoinStore);
  /** O nome da mesa a que o convite leva, quando o servidor o disse. */
  protected readonly invitedTo = computed(() => {
    const preview = this.store.preview();
    return preview.kind === 'ready' ? preview.title : '';
  });
  protected readonly invalidMessage = computed(() => {
    const preview = this.store.preview();
    return preview.kind === 'invalid' ? preview.message : '';
  });

  ngOnInit(): void {
    this.store.tableId.set(this.tableId());
    this.store.code.set(this.invite() ?? '');
    void this.store.loadPreview(); // sem o código no link, não há o que perguntar: fica o texto genérico
  }
}
