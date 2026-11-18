import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Injector,
  afterNextRender,
  computed,
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
  templateUrl: './table-page.html',
  styleUrl: './table-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TablePage {
  readonly tableId = input.required<string>();

  protected readonly store = inject(TableStore);

  private readonly documentTitle = inject(Title);
  private readonly feed = viewChild(FeedList);
  private lastSceneName: string | undefined;
  /** O nome da cena: o `computed` só avisa quando o texto muda, não a cada leitura nova da mesa. */
  private readonly sceneName = computed(() => this.store.scene()?.name);
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
  /** A ficha do painel da mesa larga está aberta? Só vale na sessão: ao reabrir a mesa ela volta aberta. */
  protected readonly mineOpen = signal(true);
  /** Quantos itens do feed chegaram enquanto se lia mais acima. */
  protected readonly unseen = signal(0);

  constructor() {
    publishDockHeight(this.dock);
    let wasBusy = false;
    effect(() => {
      // Uma ação própria que terminou leva a história ao fim: quem a relia acima vê a consequência do que fez.
      const busy = this.store.actionBusy();
      if (wasBusy && !busy && !this.store.actionError()) {
        this.feed()?.follow();
      }
      wasBusy = busy;
    });
    effect(() => {
      // Cada estado tem o seu `h1`: quando o da abertura some (o foco estava nele), o foco passa ao da tela nova.
      this.store.state();
      afterNextRender(() => this.refocusHeading(), { injector: this.injector });
    });
    effect(() => {
      // Só quando o NOME da cena muda (foi-se por uma saída): o botão tocado, que ganhou o foco de volta ao fechar a
      // folha, deixou de existir; se o foco se perdeu, ele passa à história. Evento novo na mesma cena não mexe no foco.
      const name = this.sceneName();
      const previous = this.lastSceneName;
      this.lastSceneName = name;
      if (previous === undefined || name === undefined || name === previous) {
        return; // a primeira cena (ao abrir a mesa) e a mesma cena não roubam o foco
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
    });
    effect(() => {
      const campaign = this.store.title();
      if (campaign) {
        this.documentTitle.setTitle(`${campaign} · Devaneio`);
      }
    });
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
