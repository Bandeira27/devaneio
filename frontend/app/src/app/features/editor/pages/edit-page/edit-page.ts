import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  DestroyRef,
  OnInit,
  effect,
  inject,
  input,
  signal,
} from '@angular/core';
import { RouterLink, RouterOutlet } from '@angular/router';
import { DvBadge } from '@shared/ui/badge/badge';
import { DvButton } from '@shared/ui/button/button';
import { DvNotice } from '@shared/ui/notice/notice';
import { DvState } from '@shared/ui/state/state';
import { focusElement } from '@shared/ui/focus';
import { EditorStore } from '../../editor.store';
import { DvIcon } from '../../../../shared/ui/icon/icon';

/** Quanto a conferência espera (ms) antes de dizer "Conferindo…". */
const SLOW_CHECK_MS = 300;

/**
 * O roteiro de uma campanha (a tela de edição): a situação da conferência (o servidor confere a cada edição e
 * os erros e avisos vêm em português), e a barra de gravar. Gravar fica bloqueado com o motivo escrito enquanto houver
 * erro; uma campanha que já tem mesa só se grava como cópia. As seções (locais, NPCs, facções...) são páginas filhas e o menu delas é a barra lateral da campanha. Tem o próprio
 * `EditorStore`, que as seções injetam.
 */
@Component({
  selector: 'dv-editor-page',
  imports: [DvIcon, RouterLink, RouterOutlet, DvBadge, DvButton, DvNotice, DvState],
  providers: [EditorStore],
  templateUrl: './edit-page.html',
  styleUrl: './edit-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '(window:beforeunload)': 'warnBeforeUnload($event)' },
})
export class EditorPage implements OnInit {
  /** O id da rota: o de uma campanha da pasta, ou `nova`. */
  readonly campaignId = input.required<string>();
  /** Com `nova`: o id da campanha de que esta é uma cópia. */
  readonly copia = input('');

  protected readonly store = inject(EditorStore);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  /**
   * A conferência está demorando (passou de `SLOW_CHECK_MS`): só então aparece "Conferindo…". Uma conferência rápida não
   * troca o selo de "Sem erros" por outro e de volta a cada pausa na digitação; o último resultado fica à vista.
   */
  protected readonly checkingSlowly = signal(false);
  private slowTimer: ReturnType<typeof setTimeout> | undefined;

  constructor() {
    effect(() => {
      const validating = this.store.validating();
      clearTimeout(this.slowTimer);
      if (validating) {
        this.slowTimer = setTimeout(() => this.checkingSlowly.set(true), SLOW_CHECK_MS);
      } else {
        this.checkingSlowly.set(false);
      }
    });
    inject(DestroyRef).onDestroy(() => clearTimeout(this.slowTimer));
  }

  ngOnInit(): void {
    void this.store.load(this.campaignId(), this.copia());
  }

  /** Salvar como cópia: o botão some junto com o aviso, então o foco vai ao título da tela (que agora diz que é uma cópia). */
  protected async copy(): Promise<void> {
    if (await this.store.startCopy()) {
      const heading = this.host.nativeElement.querySelector('h1');
      if (heading) {
        focusElement(heading);
      }
    }
  }

  /** Fechar ou recarregar a aba com alterações não gravadas pede confirmação ao navegador. */
  protected warnBeforeUnload(event: BeforeUnloadEvent): void {
    if (this.store.dirty()) {
      event.preventDefault();
    }
  }

  /** Para o guarda de saída da rota: pergunta antes de descartar alterações. */
  canLeave(): Promise<boolean> {
    return this.store.canLeave();
  }
}
