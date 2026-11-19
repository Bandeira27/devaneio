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
import { Router, RouterLink } from '@angular/router';
import { DvButton } from '@shared/ui/button/button';
import { DvDisclosure } from '@shared/ui/disclosure/disclosure';
import { DvIcon } from '@shared/ui/icon/icon';
import { DvNotice } from '@shared/ui/notice/notice';
import { DvPlayClock } from '@shared/ui/play-clock/play-clock';
import { DvState } from '@shared/ui/state/state';
import { Sheet } from '@shared/ui/sheet/sheet';
import { focusElement, isFocusFree } from '@shared/ui/focus';
import { connectionBlockOf } from '../../table.derived';
import { publishDockHeight, publishRailHeights, publishSituationHeight } from './dock-height';
import { ActionDock } from '../../components/action-dock/action-dock';
import { CharacterCard } from '../../components/character-card/character-card';
import { ConnectionBadge } from '../../components/connection-badge/connection-badge';
import { FeedList } from '../../components/feed-list/feed-list';
import { Lobby } from '../../components/lobby/lobby';
import { PartyStrip } from '../../components/party-strip/party-strip';
import { SceneCard } from '../../components/scene-card/scene-card';
import { HostAside } from '../../host/host-aside';
import { HostSession, canDock } from '../../host/host-session';
import { HostSheet } from '../../host/host-sheet';
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
    DvPlayClock,
    FeedList,
    HostAside,
    Lobby,
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
  protected readonly session = inject(HostSession);
  private readonly sheet = inject(Sheet);

  private readonly documentTitle = inject(Title);
  private readonly feed = viewChild(FeedList);
  private lastSceneName: string | undefined;
  /** O nome da cena: o `computed` só avisa quando o texto muda, não a cada leitura nova da mesa. */
  private readonly sceneName = computed(() => this.store.shownScene()?.name);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly injector = inject(Injector);
  private readonly router = inject(Router);
  private readonly story = viewChild<ElementRef<HTMLElement>>('story');
  private readonly actions = viewChild(ActionDock);
  private readonly dock = viewChild<ElementRef<HTMLElement>>('dock');
  private readonly side = viewChild<ElementRef<HTMLElement>>('side');
  private readonly situation = viewChild<ElementRef<HTMLElement>>('situation');
  /** O aviso de conexão perdida (o mesmo texto que bloqueia as ações), ou `''`. */
  protected readonly connectionNotice = computed(() => {
    const status = this.store.liveStatus();
    return status === 'expired' || status === 'gone' ? connectionBlockOf(status) : '';
  });
  /** Avisa o leitor de tela que a resposta do copiloto chegou quando a barra está fechada e ele não a ouviria. */
  protected readonly copilotAlert = computed(() =>
    !this.session.open() && this.session.copilot.answer() ? 'A resposta do copiloto chegou.' : '',
  );
  /** A ficha do painel da mesa larga está aberta? Só vale na sessão: ao reabrir a mesa ela volta aberta. */
  protected readonly mineOpen = signal(true);

  constructor() {
    effect(() => {
      // O personagem é passo obrigatório de quem foi convidado: na sala sem ele, o caminho o leva ao passo que falta.
      // O anfitrião não é levado: seguir sem personagem é escolha dele.
      if (
        this.store.state() === 'ready' &&
        this.store.phase() === 'lobby' &&
        !this.store.isHost() &&
        !this.store.character()
      ) {
        void this.router.navigate(['/mesa', this.tableId(), 'personagem'], { replaceUrl: true });
      }
    });
    effect(() => {
      // A rota antiga do painel pede a barra aberta; só o anfitrião tem barra.
      if (this.session.requested() && this.store.state() === 'ready') {
        this.session.requested.set(false);
        if (this.store.isHost()) {
          this.showHost();
        }
      }
    });
    publishDockHeight(this.dock);
    publishSituationHeight(this.situation);
    publishRailHeights(this.side, this.dock);
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

  /** Abre ou fecha a barra do anfitrião: ao lado da mesa na tela larga, um bottom sheet nas outras. */
  protected toggleHost(): void {
    if (this.session.open()) {
      this.session.open.set(false);
    } else {
      this.showHost();
    }
  }

  private showHost(): void {
    if (this.session.open()) {
      return;
    }
    const docked = canDock();
    this.session.docked.set(docked);
    if (docked) {
      this.session.open.set(true);
      this.focusAfterRender('.host-aside__title');
      return;
    }
    this.session.open.set(true);
    void this.sheet
      .open(HostSheet, { label: 'Painel do anfitrião', injector: this.injector })
      .then(() => this.session.open.set(false));
  }

  /** Fecha a barra encaixada e devolve o foco ao botão que a abriu. */
  protected closeHost(): void {
    this.session.open.set(false);
    this.focusAfterRender('.table__host');
  }

  private focusAfterRender(selector: string): void {
    afterNextRender(() => this.host.nativeElement.querySelector<HTMLElement>(selector)?.focus(), {
      injector: this.injector,
    });
  }

  private refocusHeading(): void {
    const heading = this.host.nativeElement.querySelector('h1');
    if (heading && isFocusFree()) {
      focusElement(heading);
    }
  }

  /** O link "Pular para as ações": com rota por hash, `href="#..."` navegaria, então o foco é movido à mão. */
  protected skipToActions(event: Event): void {
    event.preventDefault();
    this.actions()?.focusActions();
  }
}
