import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  Injector,
  afterNextRender,
  computed,
  OnInit,
  effect,
  inject,
  input,
  signal,
  viewChild,
} from '@angular/core';
import { Title } from '@angular/platform-browser';
import { RouterLink } from '@angular/router';
import { DvButton } from '@shared/ui/button/button';
import { DvDisclosure } from '@shared/ui/disclosure/disclosure';
import { DvIcon } from '@shared/ui/icon/icon';
import { DvNotice } from '@shared/ui/notice/notice';
import { DvState } from '@shared/ui/state/state';
import { focusElement, isFocusFree } from '@shared/ui/focus';
import { connectionBlockOf } from '../../table.derived';
import { publishDockHeight } from './dock-height';
import { ActionDock } from '../../components/action-dock/action-dock';
import { CharacterCard } from '../../components/character-card/character-card';
import { ConnectionBadge } from '../../components/connection-badge/connection-badge';
import { FeedList } from '../../components/feed-list/feed-list';
import { PartyStrip } from '../../components/party-strip/party-strip';
import { SceneCard } from '../../components/scene-card/scene-card';
import { TableStore } from '../../table.store';

/** Tela da mesa: cena, grupo, feed ao vivo e as ações. */
@Component({
  selector: 'dv-table-page',
  imports: [
    CharacterCard,
    RouterLink,
    DvButton,
    DvDisclosure,
    DvIcon,
    DvNotice,
    DvState,
    ActionDock,
    ConnectionBadge,
    FeedList,
    PartyStrip,
    SceneCard,
  ],
  providers: [TableStore],
  templateUrl: './table-page.html',
  styleUrl: './table-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TablePage implements OnInit {
  readonly tableId = input.required<string>();

  protected readonly store = inject(TableStore);

  private readonly documentTitle = inject(Title);
  private readonly feed = viewChild(FeedList);
  private gone = false;
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly injector = inject(Injector);
  private readonly story = viewChild<ElementRef<HTMLElement>>('story');
  private readonly actions = viewChild(ActionDock);
  private readonly dock = viewChild<ElementRef<HTMLElement>>('dock');
  /** O aviso de conexão perdida (o mesmo texto que bloqueia as ações), ou `''`. */
  protected readonly connectionNotice = computed(() => {
    const status = this.store.liveStatus();
    return status === 'expired' || status === 'gone' ? connectionBlockOf(status) : '';
  });
  /** Quantos itens do feed chegaram enquanto se lia mais acima. */
  protected readonly unseen = signal(0);

  constructor() {
    inject(DestroyRef).onDestroy(() => (this.gone = true));
    publishDockHeight(this.dock);
    effect(() => {
      // Cada estado tem o seu `h1`: quando o da abertura some (o foco estava nele), o foco passa ao da tela nova.
      this.store.state();
      afterNextRender(() => this.refocusHeading(), { injector: this.injector });
    });
    effect(() => {
      const campaign = this.store.title();
      if (campaign) {
        this.documentTitle.setTitle(`${campaign} · Devaneio`);
      }
    });
  }

  ngOnInit(): void {
    this.store.tableId.set(this.tableId());
    void this.store.load();
  }

  /**
   * Vai por uma saída tocada na cena. A cena muda e o botão tocado (que recebe o foco de volta ao fechar a folha) deixa
   * de existir: se o foco se perdeu, ele passa à história, onde a pessoa lê o que aconteceu.
   */
  protected async goThroughExit(exitId: string): Promise<void> {
    await this.actions()?.go(exitId);
    if (this.gone) {
      return; // saiu da página com a folha aberta
    }
    afterNextRender(
      () => {
        const story = this.story()?.nativeElement;
        if (story && isFocusFree()) {
          focusElement(story);
        }
      },
      { injector: this.injector },
    );
  }

  private refocusHeading(): void {
    const heading = this.host.nativeElement.querySelector('h1');
    if (heading && isFocusFree()) {
      focusElement(heading);
    }
  }

  /** Leva a tela ao fim da história e tira o aviso de novidades. */
  protected toEnd(): void {
    this.feed()?.scrollToEnd();
    const story = this.story()?.nativeElement;
    if (story) {
      focusElement(story); // o botão some: o foco fica na história
    }
  }

  /** O link "Pular para as ações": com rota por hash, `href="#..."` navegaria, então o foco é movido à mão. */
  protected skipToActions(event: Event): void {
    event.preventDefault();
    this.actions()?.focusActions();
  }
}
