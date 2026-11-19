import { signal } from '@angular/core';
import { messageOf } from '../api/api-failure';

/**
 * Roda uma ação sobre uma mesa (arquivar, restaurar, apagar, assumir o lugar de anfitrião) e guarda o que a tela mostra: qual mesa está
 * ocupada (os botões dela ficam bloqueados, para um segundo toque não repetir o pedido) e a mensagem se a ação falhar.
 * Cada tela cria o seu: o erro de uma não aparece na outra.
 */
export class TableActionRunner {
  /** A mesa em andamento, ou `null`. */
  readonly busy = signal<string | null>(null);
  /** O que deu errado na última ação, em palavras do jogo; vazio se deu certo. */
  readonly error = signal('');

  /** Roda a ação; devolve `true` se terminou sem falha. */
  async run(tableId: string, action: () => Promise<void>): Promise<boolean> {
    this.error.set('');
    this.busy.set(tableId);
    try {
      await action();
      return true;
    } catch (failure) {
      this.error.set(messageOf(failure));
      return false;
    } finally {
      this.busy.set(null);
    }
  }
}
