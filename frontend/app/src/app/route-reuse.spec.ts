import { ActivatedRouteSnapshot } from '@angular/router';
import { ParamsAwareReuse } from './route-reuse';

function route(config: object, params: Record<string, string>): ActivatedRouteSnapshot {
  return { routeConfig: config, params } as unknown as ActivatedRouteSnapshot;
}

describe('ParamsAwareReuse', () => {
  const strategy = new ParamsAwareReuse();
  const mesa = { path: 'mesa/:tableId' };

  it('a mesma rota com os mesmos parâmetros é reaproveitada', () => {
    expect(
      strategy.shouldReuseRoute(route(mesa, { tableId: 'a' }), route(mesa, { tableId: 'a' })),
    ).toBe(true);
  });

  it('a mesma rota com outra mesa não é: a página nova carrega do zero', () => {
    expect(
      strategy.shouldReuseRoute(route(mesa, { tableId: 'b' }), route(mesa, { tableId: 'a' })),
    ).toBe(false);
  });

  it('rotas diferentes não são reaproveitadas, nem com os mesmos parâmetros', () => {
    const personagem = { path: 'mesa/:tableId/personagem' };
    expect(
      strategy.shouldReuseRoute(route(personagem, { tableId: 'a' }), route(mesa, { tableId: 'a' })),
    ).toBe(false);
  });

  it('rota sem parâmetros (o shell) continua sendo reaproveitada', () => {
    const shell = { path: '' };
    expect(strategy.shouldReuseRoute(route(shell, {}), route(shell, {}))).toBe(true);
  });
});
