import { Injectable } from '@angular/core';

/** O id da rota de uma campanha que ainda não foi gravada (o editor, o quadro da campanha e o reuso de rotas o usam). */
export const NEW_CAMPAIGN = 'nova';

/**
 * O recado "acabei de gravar a campanha nova com este id": ao gravar pela primeira vez, o editor troca o `nova` da
 * rota pelo id verdadeiro, e a tela deve continuar a mesma (com o que o autor já tinha aberto), não recomeçar. A
 * estratégia de reuso de rotas lê o recado; o editor o dá antes de navegar e o limpa depois.
 */
@Injectable({ providedIn: 'root' })
export class CreatedCampaign {
  private id: string | null = null;

  /** Anuncia o id da campanha recém-criada. */
  announce(id: string): void {
    this.id = id;
  }

  /** Esse é o id da campanha recém-criada? */
  is(id: unknown): boolean {
    return this.id !== null && this.id === id;
  }

  clear(): void {
    this.id = null;
  }
}
