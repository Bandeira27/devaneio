import {
  booleanAttribute,
  ChangeDetectionStrategy,
  Component,
  computed,
  input,
  output,
} from '@angular/core';
import { DvIcon, type IconName } from '../icon/icon';

/** O tom de um aviso: informação, confirmação, atenção ou erro. */
export type NoticeKind = 'info' | 'ok' | 'warn' | 'error';

const PREFIX: Record<NoticeKind, string> = {
  info: '',
  ok: 'Pronto: ',
  warn: 'Atenção: ',
  error: 'Erro: ',
};
const ICON: Record<NoticeKind, IconName> = {
  info: 'info',
  ok: 'ok',
  warn: 'warn',
  error: 'danger',
};

/**
 * Aviso na página, com ícone e texto (nunca só cor). Erro é `role="alert"` (o leitor de tela interrompe); os outros são
 * `status` (esperam a vez). O leitor de tela ouve o tom antes do texto, menos na informação simples.
 *
 * `dismissible` põe um botão de dispensar; `dismissed` avisa quem o mostra para tirá-lo (o erro persiste até alguém
 * dispensá-lo ou a situação mudar). Entra com a animação de entrada (`dv-enter`); para sair com `dv-leave`, o pai usa `animate.leave="dv-leave"`. O erro tem contorno sólido e mais grosso: é o único aviso que trava o fluxo.
 */
@Component({
  selector: 'dv-notice',
  imports: [DvIcon],
  templateUrl: './notice.html',
  styleUrl: './notice.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    '[class]': "'notice notice--' + kind()",
    '[class.dv-enter]': 'true', // todo aviso entra com a animação de entrada, sem cada tela precisar lembrar
    '[attr.role]': "kind() === 'error' ? 'alert' : 'status'",
  },
})
export class DvNotice {
  readonly kind = input<NoticeKind>('info');
  readonly dismissible = input(false, { transform: booleanAttribute });
  readonly dismissed = output();
  protected readonly prefix = computed(() => PREFIX[this.kind()]);
  protected readonly icon = computed(() => ICON[this.kind()]);
}
