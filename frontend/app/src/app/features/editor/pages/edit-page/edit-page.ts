import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  OnInit,
  inject,
  input,
} from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { DvBadge } from '@shared/ui/badge/badge';
import { DvButton } from '@shared/ui/button/button';
import { DvNotice } from '@shared/ui/notice/notice';
import { DvState } from '@shared/ui/state/state';
import { focusElement } from '@shared/ui/focus';
import { EditorStore } from '../../editor.store';

/** As seções do editor, na ordem do menu. */
export const SECTIONS = [
  { path: '', label: 'Visão geral' },
  { path: 'locais', label: 'Locais' },
  { path: 'npcs', label: 'NPCs' },
  { path: 'faccoes', label: 'Facções' },
  { path: 'marcos', label: 'Marcos' },
  { path: 'fatos', label: 'Fatos' },
  { path: 'previa', label: 'Prévia' },
] as const;

/**
 * A tela de edição de uma campanha: o menu das seções, a situação da conferência (o servidor confere a cada edição e
 * os erros e avisos vêm em português), e a barra de gravar. Gravar fica bloqueado com o motivo escrito enquanto houver
 * erro; uma campanha que já tem mesa só se grava como cópia. Tem o próprio `EditorStore`, que as seções injetam.
 */
@Component({
  selector: 'dv-editor-page',
  imports: [RouterLink, RouterLinkActive, RouterOutlet, DvBadge, DvButton, DvNotice, DvState],
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
  protected readonly sections = SECTIONS;
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);

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
