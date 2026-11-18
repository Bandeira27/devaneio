import { signal } from '@angular/core';
import type { Campaign, CampaignView, TableView } from '@contract/api_responses';
import { firstValueFrom } from 'rxjs';
import { ApiClient } from '@core/api/api-client';

/**
 * A foto da mesa (`GET /tables/{id}`) e da cena (a campanha), relidas quando o fluxo ao vivo avisa que a mesa
 * andou. Pedidos de leitura feitos durante uma leitura em voo viram uma leitura nova, iniciada depois do pedido:
 * assim a foto nunca fica atrás da revisão que motivou a chamada.
 */
export class TableSnapshot {
  readonly table = signal<TableView | null>(null);
  readonly campaign = signal<Campaign | CampaignView | null>(null);
  /** Quando a foto da mesa chegou (relógio do navegador, ms): o relógio de jogo anda a partir dela. */
  readonly receivedAt = signal(0);

  private refreshing: Promise<void> | null = null;
  private again = false;
  private stopped = false;

  constructor(
    private readonly api: ApiClient,
    private readonly tableId: () => string,
  ) {}

  /** A revisão da última foto, ou 0 se ainda não há. */
  revision(): number {
    return this.table()?.revision ?? 0;
  }

  /** Relê a mesa e a cena. Chamadas simultâneas compartilham a mesma promessa. */
  refresh(): Promise<void> {
    this.again = true;
    this.refreshing ??= this.drain();
    return this.refreshing;
  }

  /** Para de reler (a tela foi embora). Leituras em voo terminam, mas nenhuma nova começa. */
  stop(): void {
    this.stopped = true;
  }

  private async drain(): Promise<void> {
    try {
      while (this.again && !this.stopped) {
        this.again = false;
        try {
          const id = this.tableId();
          const [table, campaign] = await Promise.all([
            firstValueFrom(this.api.table(id)),
            firstValueFrom(this.api.campaign(id)),
          ]);
          this.table.set(table);
          this.receivedAt.set(Date.now());
          this.campaign.set(campaign);
        } catch {
          // O fluxo ao vivo já mostra a conexão; a próxima revisão tenta de novo.
          this.again = false;
        }
      }
    } finally {
      this.refreshing = null;
    }
  }
}
