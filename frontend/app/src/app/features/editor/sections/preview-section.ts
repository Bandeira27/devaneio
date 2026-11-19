import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import { DvBadge } from '@shared/ui/badge/badge';
import { DvButton } from '@shared/ui/button/button';
import { DvDisclosure } from '@shared/ui/disclosure/disclosure';
import { DvNotice } from '@shared/ui/notice/notice';
import { focusElement } from '@shared/ui/focus';
import { DvState } from '@shared/ui/state/state';
import { EditorStore } from '../editor.store';
import { DvIcon } from '../../../shared/ui/icon/icon';

/** A partir de quanto do teto o aviso do contexto do copiloto passa de "ok" para "perto do limite". */
const NEAR_LIMIT = 0.8;

/**
 * A prévia: o que cada um enxerga da campanha no começo de uma partida. O jogador (o que o `olhar` mostra), o LLM só com
 * o público e o LLM com os segredos (o que ele recebe se o anfitrião ligar `--segredos-no-llm`), para o autor conferir
 * que nenhuma nota privada nem fato oculto vaza para onde não deve; e o tamanho do contexto do copiloto frente ao
 * teto. Tudo é texto. A prévia é pedida ao servidor quando a campanha não tem erros e fica marcada como antiga depois
 * de uma edição.
 */
@Component({
  selector: 'dv-preview-section',
  imports: [DvIcon, DvBadge, DvButton, DvDisclosure, DvNotice, DvState],
  templateUrl: './preview-section.html',
  styleUrl: './preview-section.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PreviewSection {
  protected readonly store = inject(EditorStore);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  /** O anúncio curto para o leitor de tela (a região viva não repete o conteúdo da prévia). */
  protected readonly status = signal('');
  /** Dá para pedir a prévia: a conferência terminou e a campanha não tem erros. */
  protected readonly ready = computed(
    () => !this.store.validating() && this.store.report()?.ok === true,
  );
  protected readonly percent = computed(() => {
    const preview = this.store.preview();
    // Para baixo: 99,6% não pode aparecer como 100% enquanto o selo ainda diz "perto do limite".
    return preview === null || preview.copilot_limit <= 0
      ? 0
      : Math.floor((preview.copilot_chars / preview.copilot_limit) * 100);
  });
  protected readonly level = computed<'ok' | 'near' | 'over'>(() => {
    const preview = this.store.preview();
    if (preview === null) {
      return 'ok';
    }
    if (preview.copilot_chars > preview.copilot_limit) {
      return 'over';
    }
    return preview.copilot_chars >= preview.copilot_limit * NEAR_LIMIT ? 'near' : 'ok';
  });

  constructor() {
    let refreshing = false;
    effect(() => {
      // Só a atualização de uma prévia que já existe precisa de anúncio: a primeira carga tem o próprio "Preparando…".
      const loading = this.store.previewing();
      const hasPreview = untracked(() => this.store.preview() !== null);
      if (loading && hasPreview) {
        refreshing = true;
        this.status.set('Atualizando a prévia…');
      } else if (!loading && refreshing) {
        refreshing = false;
        this.status.set(
          untracked(() => this.store.previewError()) === '' ? 'Prévia atualizada.' : '',
        );
      }
    });
    effect(() => {
      // A primeira vez que a campanha está sem erros, a prévia vem sozinha; depois de uma falha ou de uma prévia antiga,
      // só pelo botão (o erro não some sozinho numa edição).
      if (
        this.ready() &&
        untracked(
          () =>
            this.store.preview() === null &&
            !this.store.previewing() &&
            this.store.previewError() === '',
        )
      ) {
        void this.store.loadPreview();
      }
    });
  }

  /** "Tentar de novo": o aviso com o botão some ao clicar, então o foco volta ao título da seção. */
  protected async retry(): Promise<void> {
    await this.store.loadPreview();
    this.focusTitle();
  }

  protected retryCheck(): void {
    this.store.recheck();
    this.focusTitle();
  }

  private focusTitle(): void {
    const title = this.host.nativeElement.querySelector<HTMLElement>('#previa-titulo');
    if (title) {
      focusElement(title);
    }
  }

  protected number(value: number): string {
    return value.toLocaleString('pt-BR');
  }
}
