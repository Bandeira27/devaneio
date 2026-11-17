import { HttpClient, HttpContext, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';
import type {
  Campaign,
  CampaignSummary,
  CampaignView,
  CommandResult,
  CopilotAnswer,
  EditorCampaign,
  EventsView,
  InvitePreview,
  RulesView,
  PreviewView,
  SayResult,
  SystemInfo,
  TableCreated,
  TableJoined,
  TableView,
  ValidationReport,
} from '@contract/api_responses';
import type {
  CommandRequest,
  CopilotRequest,
  CreateTableRequest,
  InvitePreviewRequest,
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

  /** O nome da mesa para quem tem o convite, antes de entrar (sem `Authorization`: quem entra ainda não tem token). */
  invitePreview(tableId: string, request: InvitePreviewRequest): Observable<InvitePreview> {
    return this.http.post<InvitePreview>(`${this.base(tableId)}/preview`, request);
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

  /** Pergunta ao copiloto (só o anfitrião): a resposta volta só para quem perguntou. */
  copilot(tableId: string, request: CopilotRequest): Observable<CopilotAnswer> {
    return this.http.post<CopilotAnswer>(
      `${this.base(tableId)}/copilot`,
      request,
      this.as(tableId),
    );
  }

  // --- editor de campanhas (só com `--editor`; sem ele o servidor responde 404) ----------------------------------

  /** As campanhas da pasta, com `writable` falso nas que já têm mesa. */
  editorCampaigns(): Observable<EditorCampaign[]> {
    return this.http.get<EditorCampaign[]>('/editor/campaigns');
  }

  /** A campanha inteira, para editar. */
  editorCampaign(id: string): Observable<Campaign> {
    return this.http.get<Campaign>(`/editor/campaigns/${encodeURIComponent(id)}`);
  }

  /** Confere a campanha como ela está agora; nunca grava. */
  editorValidate(campaign: Campaign): Observable<ValidationReport> {
    return this.http.post<ValidationReport>('/editor/validate', { campaign });
  }

  /** Grava uma campanha nova. */
  editorCreate(campaign: Campaign): Observable<EditorCampaign> {
    return this.http.post<EditorCampaign>('/editor/campaigns', { campaign });
  }

  /** Regrava uma campanha que nenhuma mesa usa. */
  editorUpdate(id: string, campaign: Campaign): Observable<EditorCampaign> {
    return this.http.put<EditorCampaign>(`/editor/campaigns/${encodeURIComponent(id)}`, {
      campaign,
    });
  }

  /** Os sistemas de regras que uma campanha pode citar. */
  editorSystems(): Observable<SystemInfo[]> {
    return this.http.get<SystemInfo[]>('/editor/systems');
  }

  /** As regras de um sistema (armas, habilidades...). */
  editorSystem(id: string): Observable<RulesView> {
    return this.http.get<RulesView>(`/editor/systems/${encodeURIComponent(id)}`);
  }

  /** O que o jogador e o LLM veem da campanha. */
  editorPreview(campaign: Campaign): Observable<PreviewView> {
    return this.http.post<PreviewView>('/editor/preview', { campaign });
  }

  private base(tableId: string): string {
    return `/tables/${encodeURIComponent(tableId)}`;
  }

  private as(tableId: string): { context: HttpContext } {
    return { context: new HttpContext().set(TABLE, tableId) };
  }
}
