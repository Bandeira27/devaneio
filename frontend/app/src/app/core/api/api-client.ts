import { HttpClient, HttpContext, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';
import type {
  Campaign,
  CampaignSummary,
  CampaignView,
  CommandResult,
  EventsView,
  RulesView,
  SayResult,
  TableCreated,
  TableJoined,
  TableView,
} from '@contract/api_responses';
import type {
  CommandRequest,
  CreateTableRequest,
  JoinRequest,
  SayRequest,
} from '@contract/api_requests';
import { TABLE } from './api.interceptor';
import type { EventsQuery } from './api-types';

/** Cliente tipado da API da mesa. Toda falha chega como `ApiFailure` (ver o interceptor). */
@Injectable({ providedIn: 'root' })
export class ApiClient {
  private readonly http = inject(HttpClient);

  campaigns(): Observable<CampaignSummary[]> {
    return this.http.get<CampaignSummary[]>('/campaigns');
  }

  createTable(request: CreateTableRequest): Observable<TableCreated> {
    return this.http.post<TableCreated>('/tables', request);
  }

  joinTable(tableId: string, request: JoinRequest): Observable<TableJoined> {
    return this.http.post<TableJoined>(`${this.base(tableId)}/players`, request);
  }

  table(tableId: string): Observable<TableView> {
    return this.http.get<TableView>(this.base(tableId), this.as(tableId));
  }

  rules(tableId: string): Observable<RulesView> {
    return this.http.get<RulesView>(`${this.base(tableId)}/rules`, this.as(tableId));
  }

  /** A campanha inteira para o anfitrião; a visão do que o `olhar` mostra para o jogador. */
  campaign(tableId: string): Observable<Campaign | CampaignView> {
    return this.http.get<Campaign | CampaignView>(
      `${this.base(tableId)}/campaign`,
      this.as(tableId),
    );
  }

  events(tableId: string, query: EventsQuery): Observable<EventsView> {
    const params = new HttpParams()
      .set('since', query.since)
      .set('since_talk', query.sinceTalk)
      .set('wait', query.wait);
    return this.http.get<EventsView>(`${this.base(tableId)}/events`, {
      ...this.as(tableId),
      params,
    });
  }

  command(tableId: string, request: CommandRequest): Observable<CommandResult> {
    return this.http.post<CommandResult>(
      `${this.base(tableId)}/commands`,
      request,
      this.as(tableId),
    );
  }

  say(tableId: string, request: SayRequest): Observable<SayResult> {
    return this.http.post<SayResult>(`${this.base(tableId)}/say`, request, this.as(tableId));
  }

  private base(tableId: string): string {
    return `/tables/${encodeURIComponent(tableId)}`;
  }

  private as(tableId: string): { context: HttpContext } {
    return { context: new HttpContext().set(TABLE, tableId) };
  }
}
