import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Injector,
  OnInit,
  afterNextRender,
  computed,
  inject,
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { DvButton } from '@shared/ui/button/button';
import { DvField } from '@shared/ui/field/field';
import { DvInput } from '@shared/ui/field/input';
import { DvNotice } from '@shared/ui/notice/notice';
import { DvState } from '@shared/ui/state/state';
import { HomeStore } from '../../home.store';
import { whenOf } from '@shared/game/when';
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
  private readonly injector = inject(Injector);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  /** Há mesas guardadas (ou uma acabou de ser esquecida): a tela divide em duas colunas; sem elas, uma só, centralizada. */
  protected readonly hasSaved = computed(
    () => this.store.saved().length > 0 || this.store.forgotten() !== null,
  );
  protected readonly when = (time: number): string => whenOf(time, Date.now());

  /** Esquece a mesa e leva o foco ao "Desfazer" (o botão clicado some junto com a linha). */
  protected forget(tableId: string): void {
    this.store.forget(tableId);
    this.focusLater('.home__undo');
  }

  private focusLater(selector: string): void {
    afterNextRender(() => this.host.nativeElement.querySelector<HTMLElement>(selector)?.focus(), {
      injector: this.injector,
    });
  }

  protected restore(): void {
    this.store.restore();
    this.focusLater('.saved__link');
  }

  ngOnInit(): void {
    void this.store.load();
  }
}
