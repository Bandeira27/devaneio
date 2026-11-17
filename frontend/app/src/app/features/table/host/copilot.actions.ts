import { signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { ApiClient } from '@core/api/api-client';
import { messageOf } from '@core/api/api-failure';

/**
 * A conversa avulsa do anfitrião com o copiloto: uma pergunta por vez, sem memória entre elas. A resposta fica só
 * nesta instância (a memória da página): nunca vai ao `localStorage`, à URL nem ao feed da mesa.
 */
export class CopilotActions {
  /** A última resposta, ou `''`. Troca a cada pergunta. */
  readonly answer = signal('');
  /** A pergunta que gerou `answer`, para a tela mostrar sobre o que é a resposta. */
  readonly asked = signal('');
  readonly busy = signal(false);
  readonly error = signal('');

  constructor(
    private readonly api: ApiClient,
    private readonly tableId: () => string,
  ) {}

  /** Pergunta ao copiloto; devolve se ele respondeu. Uma pergunta de cada vez. */
  async ask(text: string): Promise<boolean> {
    if (this.busy()) {
      return false;
    }
    this.busy.set(true);
    this.error.set('');
    this.answer.set('');
    try {
      const result = await firstValueFrom(this.api.copilot(this.tableId(), { text }));
      this.asked.set(text);
      this.answer.set(result.text);
      return true;
    } catch (error) {
      this.error.set(messageOf(error));
      return false;
    } finally {
      this.busy.set(false);
    }
  }

  /** Limpa a resposta e o erro da tela. */
  clear(): void {
    this.answer.set('');
    this.asked.set('');
    this.error.set('');
  }
}
