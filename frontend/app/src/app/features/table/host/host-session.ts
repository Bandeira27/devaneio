import { Injectable, inject, signal } from '@angular/core';
import { ApiClient } from '@core/api/api-client';
import { TableStore } from '../table.store';
import { CopilotActions } from './copilot.actions';

/** A partir de 80rem a barra fica ao lado da mesa; abaixo, é uma folha (o mesmo ponto de quebra de `table-page.css`). */
export function canDock(): boolean {
  return typeof matchMedia === 'function' && matchMedia('(min-width: 80rem)').matches;
}

/**
 * O que a barra do anfitrião guarda enquanto a mesa está aberta, esteja ela aberta ou não: se está aberta e a conversa
 * com o copiloto. Vive no quadro da mesa, e não no componente da barra, porque o bottom sheet destrói o componente ao
 * fechar e a resposta não pode se perder. Só na memória da página.
 */
@Injectable()
export class HostSession {
  /** A barra (ou o bottom sheet) está aberta? Sempre começa fechada: o conteúdo é privado. */
  readonly open = signal(false);
  /** A rota antiga do painel pede para abrir a barra; a página da mesa atende e baixa o pedido. */
  readonly requested = signal(false);
  /** A barra aberta está encaixada ao lado da mesa (tela larga) ou é um bottom sheet? */
  readonly docked = signal(false);
  private readonly store = inject(TableStore);
  readonly copilot = new CopilotActions(inject(ApiClient), () => this.store.tableId());
}
