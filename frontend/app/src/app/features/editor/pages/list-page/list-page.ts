import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import type { EditorCampaign } from '@contract/api_responses';
import { ApiClient } from '@core/api/api-client';
import { ApiFailure, messageOf } from '@core/api/api-failure';
import type { LoadState } from '@shared/game/load-state';
import { DvBadge } from '@shared/ui/badge/badge';
import { DvButton } from '@shared/ui/button/button';
import { DvState } from '@shared/ui/state/state';

/**
 * A lista de campanhas do editor: editar, copiar ou começar uma nova. Campanha que já tem mesa não pode ser regravada
 * (as mesas a relêem do arquivo): ela leva um selo e só se copia. Sem `--editor` no servidor a lista diz que o editor
 * está desligado.
 */
@Component({
  selector: 'dv-editor-list-page',
  imports: [RouterLink, DvBadge, DvButton, DvState],
  templateUrl: './list-page.html',
  styleUrl: './list-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class EditorListPage implements OnInit {
  private readonly api = inject(ApiClient);
  protected readonly state = signal<LoadState | 'off'>('loading');
  protected readonly error = signal('');
  protected readonly campaigns = signal<EditorCampaign[]>([]);

  ngOnInit(): void {
    void this.load();
  }

  protected async load(): Promise<void> {
    this.state.set('loading');
    this.error.set('');
    try {
      this.campaigns.set(await firstValueFrom(this.api.editorCampaigns()));
      this.state.set('ready');
    } catch (error) {
      if (error instanceof ApiFailure && error.status === 404) {
        this.state.set('off');
        return;
      }
      this.error.set(messageOf(error));
      this.state.set('failed');
    }
  }
}
