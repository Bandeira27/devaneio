import {
  ChangeDetectionStrategy,
  Component,
  booleanAttribute,
  computed,
  input,
} from '@angular/core';
import { DvBrand } from '../brand/brand';
import { DvIcon, type IconName } from '../icon/icon';
import { DvOrnament } from '../ornament/ornament';

/** O que a tela está dizendo: carregando, vazio, erro ou indisponível. */
export type StateKind = 'loading' | 'empty' | 'error' | 'unavailable';

/**
 * O estado de uma tela ou de uma região: carregando (três pontos de fumaça e `role="status"`), vazio,
 * erro (`role="alert"`) ou indisponível. A mensagem é o conteúdo; uma ação opcional (tentar de novo, voltar) entra
 * em `[dvStateAction]`. Com `cover`, vira a abertura de uma tela: marca, pontos e mensagem centralizados, com a altura
 * de uma tela, para o carregamento e a folha de transição terem a mesma forma.
 */
@Component({
  selector: 'dv-state',
  imports: [DvBrand, DvIcon, DvOrnament],
  template: `
    @if (cover()) {
      <span class="mark" aria-hidden="true"><dv-brand size="lg" /><dv-ornament /></span>
    }
    @if (kind() === 'loading') {
      <span class="pending" aria-hidden="true"><i></i><i></i><i></i></span>
    } @else {
      <dv-icon [name]="icon()" />
    }
    <p class="message"><ng-content /></p>
    <ng-content select="[dvStateAction]" />
  `,
  styleUrl: './state.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    '[class]': "'state state--' + kind()",
    '[class.state--cover]': 'cover()',
    '[attr.role]': 'role()',
  },
})
export class DvState {
  readonly kind = input<StateKind>('empty');
  /** Tela cheia de abertura: a marca, os pontos e a mensagem, centralizados (a mesma cara da folha de transição). */
  readonly cover = input(false, { transform: booleanAttribute });
  protected readonly icon = computed<IconName>(() => {
    const kind = this.kind();
    return kind === 'error' ? 'danger' : kind === 'unavailable' ? 'warn' : 'info';
  });
  protected readonly role = computed(() => {
    const kind = this.kind();
    return kind === 'error'
      ? 'alert'
      : kind === 'loading' || kind === 'unavailable'
        ? 'status'
        : null;
  });
}
