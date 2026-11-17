import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  untracked,
} from '@angular/core';
import { DvBadge } from '@shared/ui/badge/badge';
import { DvButton } from '@shared/ui/button/button';
import { DvDisclosure } from '@shared/ui/disclosure/disclosure';
import { DvNotice } from '@shared/ui/notice/notice';
import { DvState } from '@shared/ui/state/state';
import { EditorStore } from '../editor.store';

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
  imports: [DvBadge, DvButton, DvDisclosure, DvNotice, DvState],
  templateUrl: './preview-section.html',
  styleUrl: './preview-section.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PreviewSection {
  protected readonly store = inject(EditorStore);
  /** Dá para pedir a prévia: a conferência terminou e a campanha não tem erros. */
  protected readonly ready = computed(
    () => !this.store.validating() && this.store.report()?.ok === true,
  );
  protected readonly percent = computed(() => {
    const preview = this.store.preview();
    return preview === null ? 0 : Math.round((preview.copilot_chars / preview.copilot_limit) * 100);
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
    effect(() => {
      // A primeira vez que a campanha está sem erros, a prévia vem sozinha; depois, só pelo botão.
      if (
        this.ready() &&
        untracked(() => this.store.preview() === null && !this.store.previewing())
      ) {
        void this.store.loadPreview();
      }
    });
  }

  protected number(value: number): string {
    return value.toLocaleString('pt-BR');
  }
}
