import { inject } from '@angular/core';
import { ActivatedRouteSnapshot, BaseRouteReuseStrategy } from '@angular/router';
import { CreatedCampaign, NEW_CAMPAIGN } from '@core/catalog/created-campaign';

/**
 * Reaproveita o componente de uma rota só quando os parâmetros também são os mesmos. O padrão do Angular o reaproveita
 * quando só o parâmetro muda (de uma mesa para outra), e como as páginas carregam os dados em `ngOnInit`, a mesa nova
 * apareceria com os dados da antiga. Com esta regra, mesa diferente é página nova, carregada do zero.
 *
 * Uma exceção: a campanha nova que o editor acabou de gravar. O `nova` vira o id verdadeiro e a tela segue a mesma
 * (o autor não perde o que tinha aberto); só o editor anuncia isso (`CreatedCampaign`).
 */
export class ParamsAwareReuse extends BaseRouteReuseStrategy {
  private readonly created = inject(CreatedCampaign);

  override shouldReuseRoute(
    future: ActivatedRouteSnapshot,
    current: ActivatedRouteSnapshot,
  ): boolean {
    return (
      super.shouldReuseRoute(future, current) && this.sameParams(future.params, current.params)
    );
  }

  private sameParams(future: Record<string, unknown>, current: Record<string, unknown>): boolean {
    const keys = Object.keys(future);
    return (
      keys.length === Object.keys(current).length &&
      keys.every(
        (key) =>
          future[key] === current[key] ||
          (key === 'campaignId' && current[key] === NEW_CAMPAIGN && this.created.is(future[key])),
      )
    );
  }
}
