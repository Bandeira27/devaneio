import {
  ChangeDetectionStrategy,
  Component,
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
import { connectionBlockOf } from '../../table.derived';
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
    effect(() => this.store.tableId.set(this.tableId()));
    this.keepDockHeight();
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
    this.store.tableId.set(this.tableId()); // os inputs já chegaram; o effect só roda depois
    void this.store.load();
  }

  private refocusHeading(): void {
    const active = document.activeElement;
    if (active === null || active === document.body || !this.host.nativeElement.contains(active)) {
      const heading = this.host.nativeElement.querySelector('h1');
      if (heading && (active === null || active === document.body)) {
        heading.tabIndex = -1;
        heading.focus({ preventScroll: true });
      }
    }
  }

  /** Leva a tela ao fim da história e tira o aviso de novidades. */
  protected toEnd(): void {
    this.feed()?.scrollToEnd();
    this.story()?.nativeElement.focus({ preventScroll: true }); // o botão some: o foco fica na história
  }

  /** O link "Pular para as ações": com rota por hash, `href="#..."` navegaria, então o foco é movido à mão. */
  protected skipToActions(event: Event): void {
    event.preventDefault();
    this.actions()?.focusActions();
  }

  /**
   * Mede a barra de ações quando ela é fixa no pé (celular) e publica a altura em `--dv-dock-height` na raiz, para a
   * rolagem e o foco pararem acima dela. Na tela larga a barra não cobre nada e a altura é zero.
   */
  private keepDockHeight(): void {
    effect((onCleanup) => {
      const dock = this.dock()?.nativeElement;
      if (!dock || typeof ResizeObserver === 'undefined') {
        return;
      }
      // Na raiz, para o `scroll-padding-bottom` do documento (base.css) valer para tudo que ganha foco ou rola.
      const root = document.documentElement;
      const publish = (): void => {
        const fixed =
          getComputedStyle(dock).position === 'sticky' &&
          matchMedia('(max-width: 63.99rem)').matches;
        root.style.setProperty('--dv-dock-height', fixed ? `${dock.offsetHeight}px` : '0px');
      };
      const observer = new ResizeObserver(publish);
      observer.observe(dock);
      publish();
      onCleanup(() => {
        observer.disconnect();
        root.style.removeProperty('--dv-dock-height');
      });
    });
  }
}
