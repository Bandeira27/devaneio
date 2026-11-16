import { ChangeDetectionStrategy, Component, OnInit, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { DvButton } from '@shared/ui/button/button';
import { DvField } from '@shared/ui/field/field';
import { DvInput } from '@shared/ui/field/input';
import { DvNotice } from '@shared/ui/notice/notice';
import { DvState } from '@shared/ui/state/state';
import { HomeStore } from '../../home.store';
import { fieldValue } from '@shared/ui/field/field-value';

/** Tela inicial: criar uma mesa, entrar por link e retomar mesas guardadas. */
@Component({
  selector: 'dv-home-page',
  imports: [RouterLink, DvButton, DvField, DvInput, DvNotice, DvState],
  providers: [HomeStore],
  templateUrl: './home-page.html',
  styleUrl: './home-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HomePage implements OnInit {
  protected readonly fieldValue = fieldValue;
  protected readonly store = inject(HomeStore);

  ngOnInit(): void {
    void this.store.load();
  }
}
