import { TestBed } from '@angular/core/testing';
import { ActivatedRouteSnapshot } from '@angular/router';
import { CreatedCampaign } from '@core/catalog/created-campaign';
import { ParamsAwareReuse } from './route-reuse';

function route(config: object, params: Record<string, string>): ActivatedRouteSnapshot {
  return { routeConfig: config, params } as unknown as ActivatedRouteSnapshot;
}

describe('ParamsAwareReuse', () => {
  let strategy: ParamsAwareReuse;
  beforeEach(() => {
    strategy = TestBed.runInInjectionContext(() => new ParamsAwareReuse());
  });
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

  describe('a campanha nova recém-gravada', () => {
    const roteiro = { path: 'c/:campaignId' };

    it('o id verdadeiro no lugar de `nova` é a mesma tela, só se o editor o anunciou', () => {
      const created = TestBed.inject(CreatedCampaign);
      const draft = route(roteiro, { campaignId: 'nova' });
      expect(strategy.shouldReuseRoute(route(roteiro, { campaignId: 'minha' }), draft)).toBe(false);
      created.announce('minha');
      expect(strategy.shouldReuseRoute(route(roteiro, { campaignId: 'minha' }), draft)).toBe(true);
      expect(strategy.shouldReuseRoute(route(roteiro, { campaignId: 'outra' }), draft)).toBe(false);
      created.clear();
      expect(strategy.shouldReuseRoute(route(roteiro, { campaignId: 'minha' }), draft)).toBe(false);
    });

    it('o anúncio só vale para quem estava em `nova`', () => {
      const created = TestBed.inject(CreatedCampaign);
      created.announce('minha');
      const other = route(roteiro, { campaignId: 'velha' });
      expect(strategy.shouldReuseRoute(route(roteiro, { campaignId: 'minha' }), other)).toBe(false);
      created.clear();
    });
  });
});
