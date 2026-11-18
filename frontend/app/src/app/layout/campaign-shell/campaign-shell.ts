import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  input,
  signal,
} from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { CampaignCatalog } from '@core/catalog/campaign-catalog';
import { NEW_CAMPAIGN } from '@core/catalog/created-campaign';
import { DvButton } from '@shared/ui/button/button';
import { DvEmblem } from '@shared/ui/emblem/emblem';
import { DvIcon, type IconName } from '@shared/ui/icon/icon';
import { DvState } from '@shared/ui/state/state';

/** Um item da barra lateral: o rótulo, o ícone e o caminho depois de `/c/<campanha>`. */
interface NavItem {
  label: string;
  icon: IconName;
  path: string[];
  /** Só fica "atual" na rota exata (a visão geral e o começo do roteiro são prefixo das outras). */
  exact: boolean;
}

/** Um grupo de itens da barra lateral, com um título opcional. */
interface NavGroup {
  title: string;
  items: NavItem[];
}

const PLAY: NavItem[] = [
  { label: 'Visão geral', icon: 'book', path: [], exact: true },
  { label: 'Mesas', icon: 'table', path: ['mesas'], exact: false },
];

const SCRIPT: NavItem[] = [
  { label: 'Geral', icon: 'scroll', path: ['roteiro'], exact: true },
  { label: 'Locais', icon: 'map', path: ['roteiro', 'locais'], exact: false },
  { label: 'NPCs', icon: 'person', path: ['roteiro', 'npcs'], exact: false },
  { label: 'Facções', icon: 'flag', path: ['roteiro', 'faccoes'], exact: false },
  { label: 'Marcos', icon: 'go', path: ['roteiro', 'marcos'], exact: false },
  { label: 'Fatos', icon: 'info', path: ['roteiro', 'fatos'], exact: false },
  { label: 'Prévia', icon: 'eye', path: ['roteiro', 'previa'], exact: false },
];

/**
 * O quadro de uma campanha: a barra lateral para navegar entre as partes dela (visão geral, mesas e, com o editor
 * ligado, o roteiro) e, ao lado, a página escolhida. A partir de 56rem a barra é uma coluna fixa; abaixo disso ela fica
 * recolhida atrás do botão "Menu" e se abre no lugar, acima do conteúdo. A campanha nova (`nova`) só tem o roteiro.
 *
 * Teclado e leitor de tela: a barra é um `<nav>` com nome, o item da página atual leva `aria-current="page"` e o botão
 * do menu diz se está aberto (`aria-expanded`). Cada página tem o seu próprio `h1`.
 */
@Component({
  selector: 'dv-campaign-shell',
  imports: [RouterLink, RouterLinkActive, RouterOutlet, DvButton, DvEmblem, DvIcon, DvState],
  templateUrl: './campaign-shell.html',
  styleUrl: './campaign-shell.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CampaignShell implements OnInit {
  /** O id da campanha na rota (`/c/:campaignId`), ou `nova`. */
  readonly campaignId = input.required<string>();

  protected readonly catalog = inject(CampaignCatalog);
  protected readonly menuOpen = signal(false);
  /** A busca da campanha terminou (achando ou não). */
  protected readonly resolved = signal(false);

  protected readonly isNew = computed(() => this.campaignId() === NEW_CAMPAIGN);
  protected readonly campaign = computed(() => this.catalog.find(this.campaignId()));
  /**
   * Não existe essa campanha neste servidor. Enquanto o catálogo é relido (acabou de ser gravada pelo editor) ainda
   * não se sabe, então o quadro segue aberto.
   */
  protected readonly missing = computed(
    () => !this.isNew() && this.campaign() === null && !this.catalog.busy(),
  );
  protected readonly title = computed(() =>
    this.isNew() ? 'Nova campanha' : (this.campaign()?.title ?? 'Campanha'),
  );
  protected readonly groups = computed<NavGroup[]>(() => {
    const groups: NavGroup[] = [];
    if (!this.isNew()) {
      groups.push({ title: '', items: PLAY });
    }
    if (this.isNew() || this.catalog.editorAvailable()) {
      groups.push({ title: 'Roteiro', items: SCRIPT });
    }
    return groups;
  });

  async ngOnInit(): Promise<void> {
    await this.catalog.ensure();
    if (!this.isNew() && this.campaign() === null) {
      await this.catalog.load(); // a campanha pode ter acabado de ser gravada pelo editor
    }
    this.resolved.set(true);
  }

  protected toggleMenu(): void {
    this.menuOpen.update((open) => !open);
  }

  protected closeMenu(): void {
    this.menuOpen.set(false);
  }
}
