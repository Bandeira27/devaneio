import { ActivatedRouteSnapshot, BaseRouteReuseStrategy } from '@angular/router';

/**
 * Reaproveita o componente de uma rota só quando os parâmetros também são os mesmos. O padrão do Angular o reaproveita
 * quando só o parâmetro muda (de uma mesa para outra), e como as páginas carregam os dados em `ngOnInit`, a mesa nova
 * apareceria com os dados da antiga. Com esta regra, mesa diferente é página nova, carregada do zero.
 */
export class ParamsAwareReuse extends BaseRouteReuseStrategy {
  override shouldReuseRoute(
    future: ActivatedRouteSnapshot,
    current: ActivatedRouteSnapshot,
  ): boolean {
    return super.shouldReuseRoute(future, current) && sameParams(future.params, current.params);
  }
}

function sameParams(a: Record<string, unknown>, b: Record<string, unknown>): boolean {
  const keys = Object.keys(a);
  return keys.length === Object.keys(b).length && keys.every((key) => a[key] === b[key]);
}
