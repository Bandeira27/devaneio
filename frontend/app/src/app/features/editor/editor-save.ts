import { Injectable, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import type { Campaign, EditorCampaign } from '@contract/api_responses';
import { ApiClient } from '@core/api/api-client';
import { messageOf } from '@core/api/api-failure';
import { CampaignCatalog } from '@core/catalog/campaign-catalog';
import { CreatedCampaign } from '@core/catalog/created-campaign';

/**
 * Gravar a campanha do editor no servidor: cria ou regrava, avisa o catálogo e, na primeira gravação, troca o `nova` do
 * endereço pelo id verdadeiro sem recomeçar a tela. Não conhece o estado da edição: quem chama diz o que gravar e aplica
 * o resultado (`onSaved`), que roda antes da navegação para o estado já estar em dia quando o endereço mudar.
 */
@Injectable()
export class EditorSave {
  private readonly api = inject(ApiClient);
  private readonly catalog = inject(CampaignCatalog);
  private readonly created = inject(CreatedCampaign);
  private readonly router = inject(Router);
  private navigating = false;

  /** Há uma gravação em andamento? */
  readonly saving = signal(false);
  /** O que deu errado na última gravação, em palavras do jogo; vazio se deu certo. */
  readonly error = signal('');

  /** A navegação que acompanha a gravação (para o endereço da campanha nova) não pede confirmação de descarte. */
  get navigatingAfterSave(): boolean {
    return this.navigating;
  }

  /** Grava (cria se `savedId` é `null`, senão regrava); devolve `true` se terminou sem falha. */
  async save(
    campaign: Campaign,
    savedId: string | null,
    onSaved: (result: EditorCampaign) => void,
  ): Promise<boolean> {
    this.saving.set(true);
    this.error.set('');
    try {
      const result =
        savedId === null
          ? await firstValueFrom(this.api.editorCreate(campaign))
          : await firstValueFrom(this.api.editorUpdate(savedId, campaign));
      void this.catalog.load(); // o catálogo de campanhas (título, novidade) acompanha o que foi gravado
      onSaved(result);
      if (savedId === null) {
        await this.followToCreated(result.id);
      }
      return true;
    } catch (error) {
      this.error.set(messageOf(error));
      return false;
    } finally {
      this.saving.set(false);
    }
  }

  /** Troca o `nova` do endereço pelo id gravado; a tela segue a mesma, só o endereço muda. */
  private async followToCreated(id: string): Promise<void> {
    const section = this.router.url.split('?')[0]?.split('/').slice(4) ?? []; // o que vem depois de /c/<id>/roteiro
    this.navigating = true;
    this.created.announce(id);
    try {
      await this.router.navigate(['/c', id, 'roteiro', ...section], { replaceUrl: true });
    } finally {
      this.created.clear();
      this.navigating = false;
    }
  }
}
