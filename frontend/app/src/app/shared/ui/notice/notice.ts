import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

export type NoticeKind = 'info' | 'error' | 'ok';

const PREFIX: Record<NoticeKind, string> = { info: 'Aviso: ', error: 'Erro: ', ok: 'Pronto: ' };

/** Aviso na página. Erro é `role="alert"` (o leitor de tela interrompe); os outros são `status` (esperam a vez). */
@Component({
  selector: 'dv-notice',
  templateUrl: './notice.html',
  styleUrl: './notice.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    '[class]': "'notice notice--' + kind()",
    '[attr.role]': "kind() === 'error' ? 'alert' : 'status'",
  },
})
export class DvNotice {
  readonly kind = input<NoticeKind>('info');
  protected readonly prefix = computed(() => PREFIX[this.kind()]);
}
